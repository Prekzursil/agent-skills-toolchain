"""Append-only JSONL tracing for CRCP operations.

Trace records intentionally have a fixed, metadata-only schema.  Callers should
store payloads elsewhere and use ``event_key`` to correlate records.
"""

from __future__ import annotations

import json
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Return an RFC 3339-compatible UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _required_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _duration(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("duration_ms must be a number")
    if not math.isfinite(value) or value < 0:
        raise ValueError("duration_ms must be finite and non-negative")
    return value


class JsonlTraceWriter:
    """Thread-safe append-only trace writer with optional size rotation.

    ``max_bytes=None`` disables rotation.  When enabled, ``backup_count`` files
    are retained as ``<name>.1`` through ``<name>.<backup_count>``.  A record
    larger than ``max_bytes`` is written intact rather than split.

    Rotation is coordinated between threads sharing this writer.  Processes
    that share a path should instead use one writer process or an external
    process lock.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int | None = None,
        backup_count: int = 3,
        fsync: bool = False,
    ):
        self.path = Path(path)
        if max_bytes is not None:
            if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
                raise TypeError("max_bytes must be an integer or None")
            if max_bytes <= 0:
                raise ValueError("max_bytes must be positive")
        if isinstance(backup_count, bool) or not isinstance(backup_count, int):
            raise TypeError("backup_count must be an integer")
        if backup_count < 0:
            raise ValueError("backup_count must be non-negative")
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.fsync = bool(fsync)
        self._lock = threading.Lock()

    def append(
        self,
        *,
        event_key: str,
        kind: str,
        rail: str,
        duration_ms: float | int,
        outcome: str,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Validate and append one trace record, returning the written record."""
        record: dict[str, Any] = {
            "timestamp": _required_text(
                "timestamp", timestamp if timestamp is not None else utc_now()
            ),
            "event_key": _required_text("event_key", event_key),
            "kind": _required_text("kind", kind),
            "rail": _required_text("rail", rail),
            "duration_ms": _duration(duration_ms),
            "outcome": _required_text("outcome", outcome),
        }
        encoded = (json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
            "utf-8"
        )

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed(len(encoded))
            with self.path.open("ab") as stream:
                stream.write(encoded)
                stream.flush()
                if self.fsync:
                    os.fsync(stream.fileno())
        return record

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if self.max_bytes is None or not self.path.is_file():
            return
        current_bytes = self.path.stat().st_size
        if current_bytes == 0 or current_bytes + incoming_bytes <= self.max_bytes:
            return

        if self.backup_count == 0:
            with self.path.open("wb"):
                pass
            return

        oldest = Path(f"{self.path}.{self.backup_count}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            source = Path(f"{self.path}.{index}")
            if source.exists():
                os.replace(source, Path(f"{self.path}.{index + 1}"))
        os.replace(self.path, Path(f"{self.path}.1"))


def append_trace(
    path: str | Path,
    *,
    event_key: str,
    kind: str,
    rail: str,
    duration_ms: float | int,
    outcome: str,
    timestamp: str | None = None,
    fsync: bool = False,
) -> dict[str, Any]:
    """Append one unrotated record; reuse ``JsonlTraceWriter`` for hot paths."""
    return JsonlTraceWriter(path, fsync=fsync).append(
        event_key=event_key,
        kind=kind,
        rail=rail,
        duration_ms=duration_ms,
        outcome=outcome,
        timestamp=timestamp,
    )


__all__ = ["JsonlTraceWriter", "append_trace", "utc_now"]
