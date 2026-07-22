"""Durable SQLite event spool for the CRCP live bridge."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


def _crcp_root() -> Path:
    return Path(__file__).resolve().parents[1]


DEFAULT_SPOOL_PATH = _crcp_root() / "reports" / "spool.db"
_PUBLISHABLE_STATES = ("spooled", "failed", "publishing")


def _payload_bytes(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def event_key(conversation_id: str, update_time: Any, payload: Any) -> str:
    """Return the stable logical identity for an observed conversation update."""
    digest = hashlib.sha256(_payload_bytes(payload)).hexdigest()
    return f"{conversation_id}|{update_time}|{digest}"


class EventSpool:
    """Small, process-safe durable spool backed by SQLite.

    Connections are intentionally short-lived so a later delivery worker can use
    this class from another thread or process without sharing connection state.
    """

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else DEFAULT_SPOOL_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        # DELETE journal (not WAL): WAL leaves -wal/-shm handles that break
        # Windows TemporaryDirectory cleanup and short-lived agent processes.
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_key TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    update_time TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('observed', 'spooled', 'publishing', 'acked', 'failed')
                    ),
                    observed_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    publish_attempts INTEGER NOT NULL DEFAULT 0,
                    acked_at REAL,
                    last_error TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS events_state_age ON events(state, observed_at)"
            )
            # A publishing row at process startup represents an interrupted send.
            # Requeue it for at-least-once delivery; consumers use event_key to dedupe.
            connection.execute(
                "UPDATE events SET state = 'spooled', updated_at = ? WHERE state = 'publishing'",
                (time.time(),),
            )

    def put_observed(self, conversation_id: str, update_time: Any, payload: Any) -> str:
        """Durably record an observation, idempotently, and return its event key."""
        payload_bytes = _payload_bytes(payload)
        key = event_key(conversation_id, update_time, payload_bytes)
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO events (
                    event_key, conversation_id, update_time, payload, state,
                    observed_at, updated_at
                ) VALUES (?, ?, ?, ?, 'observed', ?, ?)
                """,
                (key, conversation_id, str(update_time), payload_bytes, now, now),
            )
        return key

    def _set_state(
        self,
        key: str,
        state: str,
        *,
        error: str | None = None,
        allowed: tuple[str, ...] | None = None,
    ) -> bool:
        now = time.time()
        where = "event_key = ?"
        params: list[Any] = [state, now, error]
        if allowed:
            where += f" AND state IN ({','.join('?' for _ in allowed)})"
            tail: list[Any] = [key, *allowed]
        else:
            tail = [key]
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE events SET state = ?, updated_at = ?, last_error = ? WHERE {where}",
                (*params, *tail),
            )
            return cursor.rowcount == 1

    def mark_spooled(self, key: str) -> bool:
        return self._set_state(
            key, "spooled", allowed=("observed", "spooled", "failed")
        )

    def mark_publishing(self, key: str) -> bool:
        now = time.time()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE events
                SET state = 'publishing', updated_at = ?, publish_attempts = publish_attempts + 1,
                    last_error = NULL
                WHERE event_key = ? AND state IN ('spooled', 'failed')
                """,
                (now, key),
            )
            return cursor.rowcount == 1

    def claim_for_publish(self, key: str | None = None) -> dict[str, Any] | None:
        """Atomically claim one non-ACKed event and return its stored payload."""
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if key is None:
                row = connection.execute(
                    """
                    SELECT * FROM events
                    WHERE state IN ('spooled', 'failed')
                    ORDER BY observed_at, event_key LIMIT 1
                    """
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM events
                    WHERE event_key = ? AND state IN ('spooled', 'failed')
                    """,
                    (key,),
                ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                """
                UPDATE events
                SET state = 'publishing', updated_at = ?, publish_attempts = publish_attempts + 1,
                    last_error = NULL
                WHERE event_key = ?
                """,
                (now, row["event_key"]),
            )
            connection.commit()
            result = dict(row)
            result["state"] = "publishing"
            result["publish_attempts"] = int(result["publish_attempts"]) + 1
            return result

    def mark_acked(self, key: str) -> bool:
        now = time.time()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE events
                SET state = 'acked', updated_at = ?, acked_at = ?, last_error = NULL
                WHERE event_key = ? AND state != 'acked'
                """,
                (now, now, key),
            )
            if cursor.rowcount == 0:
                row = connection.execute(
                    "SELECT state FROM events WHERE event_key = ?", (key,)
                ).fetchone()
                return row is not None and row["state"] == "acked"
            return True

    def mark_failed(self, key: str, error: str | BaseException | None = None) -> bool:
        message = (
            None
            if error is None
            else f"{type(error).__name__}: {error}"
            if isinstance(error, BaseException)
            else str(error)
        )
        if message is not None:
            message = message[:1000]
        return self._set_state(
            key, "failed", error=message, allowed=_PUBLISHABLE_STATES
        )

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE event_key = ?", (key,)
            ).fetchone()
            return dict(row) if row is not None else None

    def is_acked(self, key: str) -> bool:
        row = self.get(key)
        return row is not None and row["state"] == "acked"

    def backlog_stats(self) -> dict[str, int | float | None]:
        """Return non-ACKed record count and age of the oldest observation."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count, MIN(observed_at) AS oldest
                FROM events WHERE state != 'acked'
                """
            ).fetchone()
        count = int(row["count"])
        oldest = row["oldest"]
        return {
            "count": count,
            "oldest_age_seconds": max(0.0, time.time() - float(oldest))
            if oldest is not None
            else None,
        }


# Concise compatibility name for callers that prefer Spool(path).
Spool = EventSpool
