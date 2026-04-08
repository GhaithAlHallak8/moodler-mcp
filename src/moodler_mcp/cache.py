from __future__ import annotations

import json
import logging
import os
import pickle
import sqlite3
import time
from typing import Any

from moodler_mcp.config import CACHE_DB, CACHE_DISABLED, STATE_DIR

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    value      BLOB NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at);
"""

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(STATE_DIR, exist_ok=True)
        _conn = sqlite3.connect(
            CACHE_DB,
            isolation_level=None,         # autocommit
            check_same_thread=False,      # we serialize via asyncio.to_thread
        )
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(_SCHEMA)
    return _conn


def make_key(fn_name: str, kwargs: dict) -> str:
    """Build a deterministic cache key from a function name and its kwargs."""
    return f"v1:{fn_name}:{json.dumps(kwargs, sort_keys=True, default=str)}"


def get(key: str) -> Any | None:
    """Return the cached value for `key`, or None on miss / expiry / error."""
    if CACHE_DISABLED:
        return None
    try:
        row = _get_conn().execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
    except sqlite3.Error as e:
        log.warning("cache get failed for %s: %s", key, e)
        return None
    if row is None:
        return None
    value_blob, expires_at = row
    if expires_at < time.time():
        return None
    try:
        return pickle.loads(value_blob)
    except Exception as e:
        log.warning("cache unpickle failed for %s: %s", key, e)
        return None


def set(key: str, value: Any, ttl: int) -> None:
    """Store `value` under `key` with a time-to-live of `ttl` seconds."""
    if CACHE_DISABLED:
        return
    try:
        blob = pickle.dumps(value)
    except Exception as e:
        log.warning("cache pickle failed for %s: %s", key, e)
        return
    expires_at = time.time() + ttl
    try:
        _get_conn().execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, blob, expires_at),
        )
    except sqlite3.Error as e:
        log.warning("cache set failed for %s: %s", key, e)


def clear(pattern: str | None = None) -> int:
    """Delete cache entries. If `pattern` is given, only entries whose key
    contains it are deleted. Returns the number of rows deleted."""
    try:
        conn = _get_conn()
        if pattern is None:
            cur = conn.execute("DELETE FROM cache")
        else:
            cur = conn.execute(
                "DELETE FROM cache WHERE key LIKE ?", (f"%{pattern}%",)
            )
        return cur.rowcount or 0
    except sqlite3.Error as e:
        log.warning("cache clear failed (pattern=%r): %s", pattern, e)
        return 0
