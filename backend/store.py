"""Conversation + turn persistence for MoootCourt.

Three pluggable backends, selected by ``STORE_BACKEND`` in settings:

  - sqlite : single file (default for local dev) — survives restarts.
  - ddb    : DynamoDB single-table — for the deployed showcase.
  - memory : in-process dict — fallback when neither is configured.

Schema (logical; all three backends agree on shape):

  conversations(user_id, conversation_id) →
    {title, legal_area, case_description, user_position,
     created_at, updated_at, turn_count}

  turns(user_id, conversation_id, turn_n) →
    {kind, agents (JSON), follow_up_target, follow_up_text, created_at}

Public API: ``create_conversation``, ``append_turn``, ``list_conversations``,
``load_conversation``. Each picks the right backend by inspecting
``STORE_BACKEND``.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from backend.settings import (
    DDB_REGION,
    DDB_TABLE,
    SQLITE_PATH,
    STORE_BACKEND,
)

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_conv_id() -> str:
    return uuid.uuid4().hex[:12]


# ──────────────────────────────────────────────────────────────────────────
# SQLite backend
# ──────────────────────────────────────────────────────────────────────────

_sqlite_conn: Optional[sqlite3.Connection] = None
_sqlite_lock = threading.Lock()

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    user_id          TEXT NOT NULL,
    conversation_id  TEXT NOT NULL,
    title            TEXT,
    legal_area       TEXT,
    country          TEXT,
    case_description TEXT,
    user_position    TEXT,
    created_at       TEXT,
    updated_at       TEXT,
    turn_count       INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, conversation_id)
);
CREATE INDEX IF NOT EXISTS idx_conv_user_updated
    ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS turns (
    user_id          TEXT NOT NULL,
    conversation_id  TEXT NOT NULL,
    turn_n           INTEGER NOT NULL,
    kind             TEXT,
    agents           TEXT,
    follow_up_target TEXT,
    follow_up_text   TEXT,
    created_at       TEXT,
    PRIMARY KEY (user_id, conversation_id, turn_n)
);
"""


def _sqlite_migrate(conn: sqlite3.Connection) -> None:
    """Idempotent migrations applied after the CREATE TABLE pass.

    SQLite's CREATE TABLE IF NOT EXISTS won't add a column to an existing
    table, so columns introduced after first ship need an explicit ALTER
    guarded by PRAGMA table_info to avoid duplicate-column errors on
    re-run."""
    cur = conn.execute("PRAGMA table_info(conversations)")
    existing = {row["name"] for row in cur.fetchall()}
    if "country" not in existing:
        conn.execute("ALTER TABLE conversations ADD COLUMN country TEXT")
        conn.commit()
        logger.info("SQLite migration: added conversations.country")


def _sqlite() -> sqlite3.Connection:
    """Lazy connect; create parent dir + schema on first use. Thread-safe via
    a process-wide lock — sqlite3 connections aren't safe across threads
    unless ``check_same_thread=False`` AND callers serialise."""
    global _sqlite_conn
    if _sqlite_conn is None:
        with _sqlite_lock:
            if _sqlite_conn is None:
                path = Path(SQLITE_PATH)
                path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(path), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                # WAL mode allows concurrent readers alongside one writer,
                # which is required when multiple Gunicorn workers share the
                # same SQLite file. NORMAL sync is safe with WAL.
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript(_SQLITE_SCHEMA)
                conn.commit()
                _sqlite_migrate(conn)
                _sqlite_conn = conn
                logger.info("SQLite store initialised at %s", path.resolve())
    return _sqlite_conn


def _row_to_header(row: sqlite3.Row) -> Dict:
    d = dict(row)
    return d


def _sqlite_create_conversation(user_id: str, *, title: str, legal_area: str,
                                case_description: str, user_position: str,
                                country: str) -> str:
    conv_id = _new_conv_id()
    now = _now_iso()
    conn = _sqlite()
    with _sqlite_lock:
        conn.execute(
            "INSERT INTO conversations (user_id, conversation_id, title, "
            "legal_area, country, case_description, user_position, "
            "created_at, updated_at, turn_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,0)",
            (user_id, conv_id, title or "Untitled case", legal_area,
             country or "", case_description, user_position, now, now),
        )
        conn.commit()
    return conv_id


def _sqlite_append_turn(user_id: str, conv_id: str, turn: Dict) -> int:
    now = _now_iso()
    agents_json = json.dumps(turn.get("agents", {}), default=str, ensure_ascii=False)
    follow_up = turn.get("follow_up", {}) or {}
    conn = _sqlite()
    with _sqlite_lock:
        cur = conn.execute(
            "SELECT COALESCE(MAX(turn_n), 0) AS max_n FROM turns "
            "WHERE user_id=? AND conversation_id=?",
            (user_id, conv_id),
        )
        n = cur.fetchone()["max_n"] + 1

        conn.execute(
            "INSERT INTO turns (user_id, conversation_id, turn_n, kind, "
            "agents, follow_up_target, follow_up_text, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, conv_id, n,
             "followup" if follow_up else "initial",
             agents_json,
             follow_up.get("target"),
             follow_up.get("text"),
             now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at=?, turn_count=? "
            "WHERE user_id=? AND conversation_id=?",
            (now, n, user_id, conv_id),
        )
        conn.commit()
    return n


def _sqlite_list_conversations(user_id: str, limit: int) -> List[Dict]:
    conn = _sqlite()
    with _sqlite_lock:
        cur = conn.execute(
            "SELECT * FROM conversations WHERE user_id=? "
            "ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [_row_to_header(r) for r in cur.fetchall()]


def _sqlite_load_conversation(user_id: str, conv_id: str) -> Optional[Dict]:
    conn = _sqlite()
    with _sqlite_lock:
        h_cur = conn.execute(
            "SELECT * FROM conversations WHERE user_id=? AND conversation_id=?",
            (user_id, conv_id),
        )
        header_row = h_cur.fetchone()
        if header_row is None:
            return None
        t_cur = conn.execute(
            "SELECT * FROM turns WHERE user_id=? AND conversation_id=? "
            "ORDER BY turn_n ASC",
            (user_id, conv_id),
        )
        turn_rows = t_cur.fetchall()

    header_dict = _row_to_header(header_row)
    turns = []
    for r in turn_rows:
        d = dict(r)
        try:
            d["agents"] = json.loads(d.get("agents") or "{}")
        except json.JSONDecodeError:
            d["agents"] = {}
        # Reconstruct the same shape the pipeline produced. ``country`` may
        # be NULL on rows from before the migration — default to "" so
        # downstream prompt builders treat it as Unspecified.
        d["case_description"] = header_dict.get("case_description")
        d["legal_area"] = header_dict.get("legal_area")
        d["user_position"] = header_dict.get("user_position")
        d["country"] = header_dict.get("country") or ""
        if d.get("follow_up_target") or d.get("follow_up_text"):
            d["follow_up"] = {
                "target": d.get("follow_up_target"),
                "text": d.get("follow_up_text"),
            }
        turns.append(d)
    return {"header": header_dict, "turns": turns}


# ──────────────────────────────────────────────────────────────────────────
# DynamoDB backend  (unchanged from previous version)
# ──────────────────────────────────────────────────────────────────────────

_ddb_table = None


def _ddb() -> "boto3.resources.factory.dynamodb.Table":
    global _ddb_table
    if _ddb_table is None:
        import boto3
        _ddb_table = boto3.resource("dynamodb", region_name=DDB_REGION).Table(DDB_TABLE)
    return _ddb_table


def _ddb_serialise_turn(turn: Dict) -> Dict:
    return {**turn, "agents": json.dumps(turn["agents"], default=str)}


def _ddb_deserialise_turn(item: Dict) -> Dict:
    out = dict(item)
    if isinstance(out.get("agents"), str):
        try:
            out["agents"] = json.loads(out["agents"])
        except json.JSONDecodeError:
            pass
    return out


def _ddb_create_conversation(user_id: str, *, title: str, legal_area: str,
                             case_description: str, user_position: str,
                             country: str) -> str:
    conv_id = _new_conv_id()
    now = _now_iso()
    _ddb().put_item(Item={
        "PK": f"USER#{user_id}", "SK": f"CONV#{conv_id}",
        "kind": "conversation", "conversation_id": conv_id,
        "title": title or "Untitled case", "legal_area": legal_area,
        "country": country or "",
        "case_description": case_description, "user_position": user_position,
        "created_at": now, "updated_at": now, "turn_count": 0,
    })
    return conv_id


def _ddb_append_turn(user_id: str, conv_id: str, turn: Dict) -> int:
    from boto3.dynamodb.conditions import Key
    table = _ddb()
    sk_prefix = f"CONV#{conv_id}#TURN#"
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
                               & Key("SK").begins_with(sk_prefix),
    )
    n = len(resp.get("Items", [])) + 1
    item = {
        "PK": f"USER#{user_id}", "SK": f"{sk_prefix}{n:04d}",
        "kind": "turn", "conversation_id": conv_id, "turn_n": n,
        "created_at": _now_iso(),
        **_ddb_serialise_turn(turn),
    }
    table.put_item(Item=item)
    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"CONV#{conv_id}"},
        UpdateExpression="SET updated_at = :u, turn_count = :n",
        ExpressionAttributeValues={":u": item["created_at"], ":n": n},
    )
    return n


def _ddb_list_conversations(user_id: str, limit: int) -> List[Dict]:
    from boto3.dynamodb.conditions import Key, Attr
    resp = _ddb().query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
                               & Key("SK").begins_with("CONV#"),
        FilterExpression=Attr("kind").eq("conversation"),
        ScanIndexForward=False,
        Limit=limit * 5,
    )
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items[:limit]


def _ddb_load_conversation(user_id: str, conv_id: str) -> Optional[Dict]:
    from boto3.dynamodb.conditions import Key
    resp = _ddb().query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
                               & Key("SK").begins_with(f"CONV#{conv_id}"),
    )
    items = resp.get("Items", [])
    if not items:
        return None
    header = next((i for i in items if i.get("kind") == "conversation"), None)
    turns = sorted(
        (_ddb_deserialise_turn(i) for i in items if i.get("kind") == "turn"),
        key=lambda t: t.get("turn_n", 0),
    )
    # Header attributes that the pipeline also reads off each turn. ``country``
    # may be missing on items from before the field was added.
    if header:
        for t in turns:
            t.setdefault("case_description", header.get("case_description"))
            t.setdefault("legal_area", header.get("legal_area"))
            t.setdefault("user_position", header.get("user_position"))
            t.setdefault("country", header.get("country") or "")
    return {"header": header, "turns": turns}


# ──────────────────────────────────────────────────────────────────────────
# In-memory fallback
# ──────────────────────────────────────────────────────────────────────────

_mem: Dict[str, Dict[str, Dict]] = {}  # user_id → {sk → item}


def _mem_create_conversation(user_id: str, *, title: str, legal_area: str,
                             case_description: str, user_position: str,
                             country: str) -> str:
    conv_id = _new_conv_id()
    now = _now_iso()
    _mem.setdefault(user_id, {})[f"CONV#{conv_id}"] = {
        "kind": "conversation", "conversation_id": conv_id,
        "title": title or "Untitled case", "legal_area": legal_area,
        "country": country or "",
        "case_description": case_description, "user_position": user_position,
        "created_at": now, "updated_at": now, "turn_count": 0,
    }
    return conv_id


def _mem_append_turn(user_id: str, conv_id: str, turn: Dict) -> int:
    bucket = _mem.setdefault(user_id, {})
    prefix = f"CONV#{conv_id}#TURN#"
    n = len([k for k in bucket if k.startswith(prefix)]) + 1
    follow_up = turn.get("follow_up", {}) or {}
    bucket[f"{prefix}{n:04d}"] = {
        "kind": "turn", "conversation_id": conv_id, "turn_n": n,
        "agents": turn.get("agents", {}),
        "case_description": turn.get("case_description"),
        "legal_area": turn.get("legal_area"),
        "user_position": turn.get("user_position"),
        "follow_up": follow_up if follow_up else None,
        "created_at": _now_iso(),
    }
    header = bucket.get(f"CONV#{conv_id}")
    if header:
        header["updated_at"] = _now_iso()
        header["turn_count"] = n
    return n


def _mem_list_conversations(user_id: str, limit: int) -> List[Dict]:
    bucket = _mem.get(user_id, {})
    items = [v for k, v in bucket.items()
             if k.startswith("CONV#") and v.get("kind") == "conversation"]
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items[:limit]


def _mem_load_conversation(user_id: str, conv_id: str) -> Optional[Dict]:
    bucket = _mem.get(user_id, {})
    header = bucket.get(f"CONV#{conv_id}")
    if header is None:
        return None
    turns = [v for k, v in bucket.items()
             if k.startswith(f"CONV#{conv_id}#TURN#")]
    turns.sort(key=lambda t: t.get("turn_n", 0))
    for t in turns:
        t.setdefault("case_description", header.get("case_description"))
        t.setdefault("legal_area", header.get("legal_area"))
        t.setdefault("user_position", header.get("user_position"))
        t.setdefault("country", header.get("country") or "")
    return {"header": header, "turns": turns}


# ──────────────────────────────────────────────────────────────────────────
# Public API — routes by STORE_BACKEND
# ──────────────────────────────────────────────────────────────────────────

def create_conversation(user_id: str, *, title: str, legal_area: str,
                        case_description: str, user_position: str,
                        country: str = "") -> str:
    if STORE_BACKEND == "sqlite":
        return _sqlite_create_conversation(
            user_id, title=title, legal_area=legal_area,
            case_description=case_description, user_position=user_position,
            country=country)
    if STORE_BACKEND == "ddb":
        return _ddb_create_conversation(
            user_id, title=title, legal_area=legal_area,
            case_description=case_description, user_position=user_position,
            country=country)
    return _mem_create_conversation(
        user_id, title=title, legal_area=legal_area,
        case_description=case_description, user_position=user_position,
        country=country)


def append_turn(user_id: str, conv_id: str, turn: Dict) -> int:
    if STORE_BACKEND == "sqlite":
        return _sqlite_append_turn(user_id, conv_id, turn)
    if STORE_BACKEND == "ddb":
        return _ddb_append_turn(user_id, conv_id, turn)
    return _mem_append_turn(user_id, conv_id, turn)


def list_conversations(user_id: str, *, limit: int = 50) -> List[Dict]:
    try:
        if STORE_BACKEND == "sqlite":
            return _sqlite_list_conversations(user_id, limit)
        if STORE_BACKEND == "ddb":
            return _ddb_list_conversations(user_id, limit)
        return _mem_list_conversations(user_id, limit)
    except Exception:
        logger.exception("list_conversations failed for user %s", user_id)
        return []


def load_conversation(user_id: str, conv_id: str) -> Optional[Dict]:
    try:
        if STORE_BACKEND == "sqlite":
            return _sqlite_load_conversation(user_id, conv_id)
        if STORE_BACKEND == "ddb":
            return _ddb_load_conversation(user_id, conv_id)
        return _mem_load_conversation(user_id, conv_id)
    except Exception:
        logger.exception("load_conversation failed user=%s conv=%s", user_id, conv_id)
        return None
