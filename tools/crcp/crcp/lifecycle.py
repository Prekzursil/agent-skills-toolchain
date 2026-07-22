"""CRCP event delivery lifecycle primitives.

The lifecycle deliberately separates observation, durable spooling, an active
publish attempt, and acknowledgement.  This makes checkpointing independent
from transport success and gives callers an explicit retry/dead-letter path.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class LifecycleState(str, Enum):
    """Stable wire values for an event's delivery state."""

    OBSERVED = "observed"
    SPOOLED = "spooled"
    PUBLISHING = "publishing"
    ACKED = "acked"
    DEAD_LETTER = "dead_letter"
    FAILED = "failed"


OBSERVED = LifecycleState.OBSERVED.value
SPOOLED = LifecycleState.SPOOLED.value
PUBLISHING = LifecycleState.PUBLISHING.value
ACKED = LifecycleState.ACKED.value
DEAD_LETTER = LifecycleState.DEAD_LETTER.value
FAILED = LifecycleState.FAILED.value

STATES = frozenset(state.value for state in LifecycleState)

# ACKED and DEAD_LETTER are terminal.  FAILED records may be re-spooled after
# an operator or recovery worker has addressed the failure.  A publish failure
# returns to SPOOLED when it is retryable, or moves to FAILED/DEAD_LETTER when
# it requires intervention or has exhausted its retry policy.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    OBSERVED: frozenset({SPOOLED, FAILED}),
    SPOOLED: frozenset({PUBLISHING, FAILED, DEAD_LETTER}),
    PUBLISHING: frozenset({ACKED, SPOOLED, FAILED, DEAD_LETTER}),
    ACKED: frozenset(),
    DEAD_LETTER: frozenset(),
    FAILED: frozenset({SPOOLED, DEAD_LETTER}),
}


class LifecycleError(ValueError):
    """Base exception for malformed lifecycle data."""


class InvalidTransitionError(LifecycleError):
    """Raised when a requested state transition is not in the contract."""

    def __init__(self, event_key: str, source: str, target: str):
        self.event_key = event_key
        self.source = source
        self.target = target
        super().__init__(
            f"invalid lifecycle transition for {event_key!r}: {source!r} -> {target!r}"
        )


def utc_now() -> str:
    """Return an unambiguous, timezone-aware ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _state_value(state: str | LifecycleState) -> str:
    value = state.value if isinstance(state, LifecycleState) else state
    if not isinstance(value, str) or value not in STATES:
        raise LifecycleError(f"unknown lifecycle state: {value!r}")
    return value


def _timestamp_value(value: str | None) -> str:
    if value is None:
        return utc_now()
    if not isinstance(value, str) or not value.strip():
        raise LifecycleError("timestamp must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LifecycleError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise LifecycleError("timestamp must include a timezone")
    return value


@dataclass
class EventRecord:
    """Current delivery state for one stable, deduplicated event key.

    ``timestamps`` maps every state reached to the most recent time it was
    entered.  ``attempts`` counts entries into ``publishing``, including the
    current attempt.  Retrying therefore follows publishing -> spooled ->
    publishing and increments the count exactly once per transport attempt.
    """

    event_key: str
    state: str = OBSERVED
    timestamps: dict[str, str] = field(default_factory=dict)
    attempts: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.event_key, str) or not self.event_key.strip():
            raise LifecycleError("event_key must be a non-empty string")
        self.state = _state_value(self.state)
        if (
            isinstance(self.attempts, bool)
            or not isinstance(self.attempts, int)
            or self.attempts < 0
        ):
            raise LifecycleError("attempts must be a non-negative integer")
        if not isinstance(self.timestamps, dict):
            raise LifecycleError("timestamps must be a mapping")
        clean: dict[str, str] = {}
        for key, value in self.timestamps.items():
            clean[_state_value(key)] = _timestamp_value(value)
        self.timestamps = clean
        if self.state not in self.timestamps:
            self.timestamps[self.state] = utc_now()

    def transition(
        self,
        target: str | LifecycleState,
        *,
        at: str | None = None,
    ) -> "EventRecord":
        """Move to ``target`` or raise :class:`InvalidTransitionError`.

        The record is only mutated after both the transition and timestamp
        validate, so a failed call leaves it unchanged.
        """
        target_value = _state_value(target)
        if target_value not in LEGAL_TRANSITIONS[self.state]:
            raise InvalidTransitionError(self.event_key, self.state, target_value)
        timestamp = _timestamp_value(at)
        self.state = target_value
        self.timestamps[target_value] = timestamp
        if target_value == PUBLISHING:
            self.attempts += 1
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot."""
        return {
            "event_key": self.event_key,
            "state": self.state,
            "timestamps": dict(self.timestamps),
            "attempts": self.attempts,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EventRecord":
        """Validate and restore a record from a JSON-style mapping."""
        if not isinstance(value, dict):
            raise LifecycleError("event record must be a mapping")
        try:
            return cls(
                event_key=value["event_key"],
                state=value.get("state", OBSERVED),
                timestamps=dict(value.get("timestamps") or {}),
                attempts=value.get("attempts", 0),
            )
        except KeyError as exc:
            raise LifecycleError("event record is missing event_key") from exc

    def copy(self) -> "EventRecord":
        """Return an independent validated copy."""
        return EventRecord.from_dict(self.to_dict())


class InMemoryLifecycleStore:
    """Thread-safe record store with optional atomic JSON snapshots.

    Returned records are copies.  All mutations stay behind the store lock so
    callers cannot accidentally bypass transition validation.
    """

    FORMAT = "crcp.lifecycle.v1"

    def __init__(self, records: Iterable[EventRecord] | None = None):
        self._records: dict[str, EventRecord] = {}
        self._lock = threading.RLock()
        for record in records or ():
            self.add(record)

    def observe(self, event_key: str, *, at: str | None = None) -> EventRecord:
        """Create an observed record, returning the existing one on replay."""
        timestamp = _timestamp_value(at)
        with self._lock:
            existing = self._records.get(event_key)
            if existing is not None:
                return existing.copy()
            record = EventRecord(event_key, timestamps={OBSERVED: timestamp})
            self._records[event_key] = record
            return record.copy()

    def add(self, record: EventRecord, *, replace: bool = False) -> EventRecord:
        """Insert a record; reject duplicate event keys unless replacing."""
        if not isinstance(record, EventRecord):
            raise TypeError("record must be an EventRecord")
        snapshot = record.copy()
        with self._lock:
            if snapshot.event_key in self._records and not replace:
                raise LifecycleError(f"duplicate event_key: {snapshot.event_key!r}")
            self._records[snapshot.event_key] = snapshot
            return snapshot.copy()

    def get(self, event_key: str) -> EventRecord | None:
        with self._lock:
            record = self._records.get(event_key)
            return record.copy() if record is not None else None

    def transition(
        self,
        event_key: str,
        target: str | LifecycleState,
        *,
        at: str | None = None,
    ) -> EventRecord:
        """Atomically validate and apply a transition to a stored record."""
        with self._lock:
            record = self._records.get(event_key)
            if record is None:
                raise KeyError(event_key)
            record.transition(target, at=at)
            return record.copy()

    def records(self) -> list[EventRecord]:
        """Return deterministic snapshots ordered by event key."""
        with self._lock:
            return [self._records[key].copy() for key in sorted(self._records)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.FORMAT,
            "records": [record.to_dict() for record in self.records()],
        }

    def dump(self, path: str | Path) -> Path:
        """Atomically persist a JSON snapshot using fsync + os.replace."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            temporary = None
            return destination
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass

    @classmethod
    def load(cls, path: str | Path) -> "InMemoryLifecycleStore":
        """Load and validate a snapshot written by :meth:`dump`."""
        source = Path(path)
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LifecycleError(
                f"cannot load lifecycle snapshot {source}: {exc}"
            ) from exc
        if not isinstance(value, dict) or value.get("format") != cls.FORMAT:
            raise LifecycleError("unsupported lifecycle snapshot format")
        records = value.get("records")
        if not isinstance(records, list):
            raise LifecycleError("lifecycle snapshot records must be a list")
        try:
            return cls(EventRecord.from_dict(item) for item in records)
        except (TypeError, ValueError) as exc:
            if isinstance(exc, LifecycleError):
                raise
            raise LifecycleError(f"invalid lifecycle snapshot: {exc}") from exc


__all__ = [
    "ACKED",
    "DEAD_LETTER",
    "FAILED",
    "LEGAL_TRANSITIONS",
    "OBSERVED",
    "PUBLISHING",
    "SPOOLED",
    "STATES",
    "EventRecord",
    "InMemoryLifecycleStore",
    "InvalidTransitionError",
    "LifecycleError",
    "LifecycleState",
    "utc_now",
]
