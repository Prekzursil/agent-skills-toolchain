"""Reference idempotency key and durable spool for CRCP contract tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


STATES = ("observed", "spooled", "publishing", "acked")


def payload_sha256(payload: bytes | str | Any) -> str:
    """Return a deterministic digest for bytes, text, or JSON-compatible data."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def make_event_key(
    conversation_id: str, update_time: str | int | float, payload: Any
) -> str:
    """Build the specified conversation/update/payload idempotency identity."""
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("conversation_id must be a non-empty string")
    if update_time is None or isinstance(update_time, bool):
        raise ValueError("update_time is required")
    return f"{conversation_id}:{update_time}:{payload_sha256(payload)}"


class EventSpool:
    """Small SQLite spool whose unique event key survives process restarts."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                state TEXT NOT NULL CHECK (
                    state IN ('observed', 'spooled', 'publishing', 'acked')
                )
            )
            """
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def observe(self, event_key: str, payload: Any) -> bool:
        """Insert once; return False when the logical event already exists."""
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        cur = self._db.execute(
            "INSERT OR IGNORE INTO events(event_key, payload, state) VALUES (?, ?, ?)",
            (event_key, encoded, "observed"),
        )
        self._db.commit()
        return cur.rowcount == 1

    def transition(self, event_key: str, state: str) -> None:
        if state not in STATES:
            raise ValueError(f"invalid spool state: {state}")
        row = self._db.execute(
            "SELECT state FROM events WHERE event_key = ?", (event_key,)
        ).fetchone()
        if row is None:
            raise KeyError(event_key)
        old_index = STATES.index(row[0])
        new_index = STATES.index(state)
        if new_index != old_index + 1:
            raise ValueError(f"invalid transition: {row[0]} -> {state}")
        self._db.execute(
            "UPDATE events SET state = ? WHERE event_key = ?", (state, event_key)
        )
        self._db.commit()

    def state(self, event_key: str) -> str | None:
        row = self._db.execute(
            "SELECT state FROM events WHERE event_key = ?", (event_key,)
        ).fetchone()
        return row[0] if row else None

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def __enter__(self) -> "EventSpool":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
