"""DynamoDB single-table store for conversations and turns.

Schema (table `counselai-{env}`):

  PK = USER#<user_id>
  SK = CONV#<conv_id>                   ← conversation header
  SK = CONV#<conv_id>#TURN#<n>           ← per-turn snapshot

If `DDB_TABLE` is unset (PERSISTENCE_ENABLED == False), this module falls
back to an in-process dict so the app still works in local dev / single-user
demos without AWS credentials.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.settings import DDB_TABLE, DDB_REGION, PERSISTENCE_ENABLED

logger = logging.getLogger(__name__)

# Lazy boto3 client (so unit tests / local dev without AWS creds still import)
_table = None


def _get_table():
    global _table
    if _table is None and PERSISTENCE_ENABLED:
        import boto3
        _table = boto3.resource("dynamodb", region_name=DDB_REGION).Table(DDB_TABLE)
    return _table


# ── In-memory fallback ─────────────────────────────────────────────────────
_mem: Dict[str, Dict[str, Dict]] = {}  # user_id → {sk → item}


def _mem_put(user_id: str, sk: str, item: Dict) -> None:
    _mem.setdefault(user_id, {})[sk] = item


def _mem_query_prefix(user_id: str, sk_prefix: str) -> List[Dict]:
    bucket = _mem.get(user_id, {})
    return [v for k, v in bucket.items() if k.startswith(sk_prefix)]


# ── Public API ─────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _serialise_turn(turn: Dict) -> Dict:
    """DynamoDB doesn't accept arbitrary Python objects in nested dicts;
    we JSON-encode the agent payloads for safety."""
    return {**turn, "agents": json.dumps(turn["agents"], default=str)}


def _deserialise_turn(item: Dict) -> Dict:
    out = dict(item)
    if isinstance(out.get("agents"), str):
        try:
            out["agents"] = json.loads(out["agents"])
        except json.JSONDecodeError:
            pass
    return out


def create_conversation(
    user_id: str,
    *,
    title: str,
    legal_area: str,
    case_description: str,
    user_position: str,
) -> str:
    """Insert a conversation header. Returns the new conversation_id."""
    conv_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    item = {
        "PK": f"USER#{user_id}",
        "SK": f"CONV#{conv_id}",
        "kind": "conversation",
        "conversation_id": conv_id,
        "title": title or "Untitled case",
        "legal_area": legal_area,
        "case_description": case_description,
        "user_position": user_position,
        "created_at": now,
        "updated_at": now,
        "turn_count": 0,
    }
    table = _get_table()
    if table is not None:
        table.put_item(Item=item)
    else:
        _mem_put(user_id, item["SK"], item)
    return conv_id


def append_turn(user_id: str, conv_id: str, turn: Dict) -> int:
    """Append a turn under an existing conversation. Returns the turn number."""
    sk_prefix = f"CONV#{conv_id}#TURN#"
    table = _get_table()
    if table is not None:
        # Count existing turns to assign next n. For showcase load this is
        # fine; if it grew we'd track turn_count via ATOMIC_COUNTER on header.
        from boto3.dynamodb.conditions import Key
        resp = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
                                   & Key("SK").begins_with(sk_prefix),
        )
        n = len(resp.get("Items", [])) + 1
    else:
        n = len(_mem_query_prefix(user_id, sk_prefix)) + 1

    item = {
        "PK": f"USER#{user_id}",
        "SK": f"{sk_prefix}{n:04d}",
        "kind": "turn",
        "conversation_id": conv_id,
        "turn_n": n,
        "created_at": _now_iso(),
        **_serialise_turn(turn),
    }

    if table is not None:
        table.put_item(Item=item)
        # Bump conversation header's updated_at + turn_count
        table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": f"CONV#{conv_id}"},
            UpdateExpression="SET updated_at = :u, turn_count = :n",
            ExpressionAttributeValues={":u": item["created_at"], ":n": n},
        )
    else:
        _mem_put(user_id, item["SK"], item)
        header = _mem.get(user_id, {}).get(f"CONV#{conv_id}")
        if header:
            header["updated_at"] = item["created_at"]
            header["turn_count"] = n
    return n


def list_conversations(user_id: str, *, limit: int = 50) -> List[Dict]:
    """Conversation headers (no turn rows), most-recent first."""
    sk_prefix = "CONV#"
    table = _get_table()
    if table is not None:
        from boto3.dynamodb.conditions import Key, Attr
        resp = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
                                   & Key("SK").begins_with(sk_prefix),
            FilterExpression=Attr("kind").eq("conversation"),
            ScanIndexForward=False,  # newest-first by SK; we further sort by updated_at below
            Limit=limit * 5,         # over-fetch since FilterExpression is post-query
        )
        items = resp.get("Items", [])
    else:
        items = [v for v in _mem_query_prefix(user_id, sk_prefix)
                 if v.get("kind") == "conversation"]

    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items[:limit]


def load_conversation(user_id: str, conv_id: str) -> Optional[Dict]:
    """Returns {'header': {...}, 'turns': [...]} or None if not found."""
    sk_prefix = f"CONV#{conv_id}"
    table = _get_table()
    if table is not None:
        from boto3.dynamodb.conditions import Key
        resp = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
                                   & Key("SK").begins_with(sk_prefix),
        )
        items = resp.get("Items", [])
    else:
        items = _mem_query_prefix(user_id, sk_prefix)

    if not items:
        return None

    header = next((i for i in items if i.get("kind") == "conversation"), None)
    turns = sorted(
        (_deserialise_turn(i) for i in items if i.get("kind") == "turn"),
        key=lambda t: t.get("turn_n", 0),
    )
    return {"header": header, "turns": turns}
