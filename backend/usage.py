"""Durable per-user usage controls for expensive pipeline endpoints.

The limiter is intentionally simple:

- per-user hourly quota
- per-user daily quota
- per-user concurrency cap
- cooldown window after quota exhaustion

SQLite-backed state is preferred for EC2 so counters survive restarts.
When SQLite is unavailable, an in-memory fallback keeps local development
usable without extra setup.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from backend.settings import (
    RATE_LIMIT_COOLDOWN_MINUTES,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_MAX_CONCURRENT_REQUESTS,
    RATE_LIMIT_MAX_REQUESTS_PER_DAY,
    RATE_LIMIT_MAX_REQUESTS_PER_HOUR,
    SQLITE_PATH,
    STORE_BACKEND,
)

logger = logging.getLogger(__name__)

_sqlite_conn: Optional[sqlite3.Connection] = None
_sqlite_lock = threading.Lock()
_mem_lock = threading.Lock()
_mem: Dict[str, Dict[str, int]] = {}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_limits (
    user_id            TEXT PRIMARY KEY,
    hour_window_start  INTEGER NOT NULL,
    hour_count         INTEGER NOT NULL,
    day_window_start   INTEGER NOT NULL,
    day_count          INTEGER NOT NULL,
    active_requests    INTEGER NOT NULL,
    cooldown_until     INTEGER NOT NULL,
    updated_at         TEXT NOT NULL
);
"""


class UsageLimitError(RuntimeError):
    def __init__(self, detail: str, retry_after: int):
        super().__init__(detail)
        self.detail = detail
        self.retry_after = max(1, retry_after)


@dataclass
class UsageLease:
    user_id: str
    released: bool = False


def _now_ts() -> int:
    return int(time.time())


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _hour_bucket(ts: int) -> int:
    return ts - (ts % 3600)


def _day_bucket(ts: int) -> int:
    return ts - (ts % 86400)


def _sqlite() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        with _sqlite_lock:
            if _sqlite_conn is None:
                path = Path(SQLITE_PATH)
                path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(path), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript(_SCHEMA)
                conn.commit()
                _sqlite_conn = conn
    return _sqlite_conn


def reset_active_requests() -> None:
    """On process boot, clear stale in-flight counts from previous crashes."""
    if not RATE_LIMIT_ENABLED:
        return
    try:
        if STORE_BACKEND != "sqlite":
            with _mem_lock:
                for state in _mem.values():
                    state["active_requests"] = 0
            return
        conn = _sqlite()
        with _sqlite_lock:
            conn.execute("UPDATE usage_limits SET active_requests=0")
            conn.commit()
    except Exception:
        logger.exception("reset_active_requests failed — stale in-flight counts may persist")


def _load_sqlite_state(user_id: str) -> sqlite3.Row | None:
    conn = _sqlite()
    cur = conn.execute("SELECT * FROM usage_limits WHERE user_id=?", (user_id,))
    return cur.fetchone()


def _default_state(now: int) -> Dict[str, int]:
    return {
        "hour_window_start": _hour_bucket(now),
        "hour_count": 0,
        "day_window_start": _day_bucket(now),
        "day_count": 0,
        "active_requests": 0,
        "cooldown_until": 0,
    }


def _normalise_state(state: Dict[str, int], now: int) -> Dict[str, int]:
    out = dict(state)
    if out["hour_window_start"] != _hour_bucket(now):
        out["hour_window_start"] = _hour_bucket(now)
        out["hour_count"] = 0
    if out["day_window_start"] != _day_bucket(now):
        out["day_window_start"] = _day_bucket(now)
        out["day_count"] = 0
    return out


def _breach_detail(limit: str, retry_after: int) -> str:
    minutes = max(1, retry_after // 60)
    return (
        f"Usage limit reached for {limit}. Please take a break for about "
        f"{minutes} minute{'s' if minutes != 1 else ''} before trying again."
    )


def _check_and_increment(state: Dict[str, int], now: int) -> Dict[str, int]:
    cooldown_until = state.get("cooldown_until", 0)
    if cooldown_until > now:
        raise UsageLimitError(
            _breach_detail("your account", cooldown_until - now),
            cooldown_until - now,
        )

    if state["active_requests"] >= RATE_LIMIT_MAX_CONCURRENT_REQUESTS:
        raise UsageLimitError(
            "Another analysis is already running for your account. Please wait "
            "for it to finish before starting a new one.",
            15,
        )

    if state["hour_count"] >= RATE_LIMIT_MAX_REQUESTS_PER_HOUR:
        retry_after = RATE_LIMIT_COOLDOWN_MINUTES * 60
        state["cooldown_until"] = now + retry_after
        raise UsageLimitError(_breach_detail("the hourly quota", retry_after), retry_after)

    if state["day_count"] >= RATE_LIMIT_MAX_REQUESTS_PER_DAY:
        retry_after = RATE_LIMIT_COOLDOWN_MINUTES * 60
        state["cooldown_until"] = now + retry_after
        raise UsageLimitError(_breach_detail("the daily quota", retry_after), retry_after)

    state["hour_count"] += 1
    state["day_count"] += 1
    state["active_requests"] += 1
    return state


def reserve(user_id: str) -> UsageLease:
    """Reserve one expensive request slot for `user_id`."""
    if not RATE_LIMIT_ENABLED:
        return UsageLease(user_id=user_id)

    now = _now_ts()

    if STORE_BACKEND == "sqlite":
        conn = _sqlite()
        with _sqlite_lock:
            row = _load_sqlite_state(user_id)
            state = _normalise_state(dict(row) if row else _default_state(now), now)
            try:
                updated = _check_and_increment(state, now)
            except UsageLimitError:
                conn.execute(
                    """
                    INSERT INTO usage_limits
                      (user_id, hour_window_start, hour_count, day_window_start,
                       day_count, active_requests, cooldown_until, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                      hour_window_start=excluded.hour_window_start,
                      hour_count=excluded.hour_count,
                      day_window_start=excluded.day_window_start,
                      day_count=excluded.day_count,
                      active_requests=excluded.active_requests,
                      cooldown_until=excluded.cooldown_until,
                      updated_at=excluded.updated_at
                    """,
                    (
                        user_id,
                        state["hour_window_start"],
                        state["hour_count"],
                        state["day_window_start"],
                        state["day_count"],
                        state["active_requests"],
                        state["cooldown_until"],
                        _iso_now(),
                    ),
                )
                conn.commit()
                raise

            conn.execute(
                """
                INSERT INTO usage_limits
                  (user_id, hour_window_start, hour_count, day_window_start,
                   day_count, active_requests, cooldown_until, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  hour_window_start=excluded.hour_window_start,
                  hour_count=excluded.hour_count,
                  day_window_start=excluded.day_window_start,
                  day_count=excluded.day_count,
                  active_requests=excluded.active_requests,
                  cooldown_until=excluded.cooldown_until,
                  updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    updated["hour_window_start"],
                    updated["hour_count"],
                    updated["day_window_start"],
                    updated["day_count"],
                    updated["active_requests"],
                    updated["cooldown_until"],
                    _iso_now(),
                ),
            )
            conn.commit()
        return UsageLease(user_id=user_id)

    with _mem_lock:
        state = _normalise_state(_mem.get(user_id, _default_state(now)), now)
        updated = _check_and_increment(state, now)
        _mem[user_id] = updated
    return UsageLease(user_id=user_id)


def release(lease: UsageLease | None) -> None:
    if not RATE_LIMIT_ENABLED or lease is None or lease.released:
        return

    user_id = lease.user_id
    # Mark released before the DB write so a crash below doesn't cause a
    # stuck in-flight count if the caller retries.
    lease.released = True

    try:
        if STORE_BACKEND == "sqlite":
            conn = _sqlite()
            with _sqlite_lock:
                conn.execute(
                    """
                    UPDATE usage_limits
                    SET active_requests = CASE
                        WHEN active_requests > 0 THEN active_requests - 1
                        ELSE 0
                    END,
                    updated_at = ?
                    WHERE user_id = ?
                    """,
                    (_iso_now(), user_id),
                )
                conn.commit()
        else:
            with _mem_lock:
                state = _mem.get(user_id)
                if state is not None:
                    state["active_requests"] = max(0, state.get("active_requests", 0) - 1)
    except Exception:
        logger.exception("release failed for user %s — active_requests may be inflated", user_id)
