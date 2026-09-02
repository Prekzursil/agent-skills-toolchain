"""Durable degrade-loudly sink for the marketplace revocation gate (IMP-0079).

The install gate must never fail silently when the revocation list cannot be
trusted (unreachable, rejected, expired).  Every degraded decision is recorded
here, on disk, so that a *later* reader - another process, or a new
``DegradeSink`` object on the same path - can see that installs ran in a
degraded state.  In-process return values alone are not the degrade channel.

Properties measured by the probes:

* **Durable** - each ``warn`` rewrites the sink file atomically (temporary file
  in the same directory, ``fsync``, ``os.replace``).  A failed write (for
  example ENOSPC on a full volume) raises the ``OSError`` loudly and leaves the
  previous file byte-for-byte intact; the sink is never truncated in place.
* **Bounded** - at most ``MAX_RECORDS`` (256) records are kept, oldest dropped
  first.  ``seq`` keeps increasing and ``dropped_total`` is kept, so drops stay
  visible instead of silently rewriting history.
* **Readable without the writer** - ``has_stale()`` / ``records()`` always read
  the file fresh from disk; nothing is cached in the object.

File format (``marketplace.degrade-sink/v1``)::

    {
      "schema": "marketplace.degrade-sink/v1",
      "max_records": 256,
      "next_seq": 3,
      "records": [
        {"seq": 1, "code": "STALE", "reason": "revocation list unreachable",
         "at": "2026-08-24T18:00:00Z"}
      ]
    }

The module also hosts the small clock helpers shared with ``revocation.py`` so
that tests can inject a fake clock (any object exposing ``now()``, a callable,
a fixed ``datetime``/ISO string/epoch number) and get deterministic timestamps.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "marketplace.degrade-sink/v1"
MAX_RECORDS = 256

# Warning codes.  ``STALE`` is the one the install gate propagates into
# ``Decision.warnings`` whenever it served a decision from a list it could not
# prove fresh (unreachable transport, rejected fetch, or expired freshness window).
STALE = "STALE"
REJECTED = "REJECTED"

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,63}$")

__all__ = [
    "DegradeSink",
    "DegradeSinkCorrupt",
    "MAX_RECORDS",
    "REJECTED",
    "SCHEMA",
    "STALE",
    "atomic_write_bytes",
    "clock_now",
    "iso_utc",
    "parse_iso8601",
]


class DegradeSinkCorrupt(Exception):
    """The sink file exists but is not a valid ``marketplace.degrade-sink/v1`` document."""


# --------------------------------------------------------------------------- clock


def parse_iso8601(text: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware UTC ``datetime``.

    Accepts a trailing ``Z``; a naive timestamp is taken as UTC.  Raises
    ``ValueError`` for anything that is not a timestamp.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty timestamp")
    value = text.strip()
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"not an ISO-8601 timestamp: {text!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_utc(moment: datetime) -> str:
    """Render an aware ``datetime`` as ``YYYY-MM-DDTHH:MM:SSZ`` (UTC, whole seconds)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, bool):
        raise TypeError("a bool is not a clock reading")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        return parse_iso8601(value)
    raise TypeError(f"cannot interpret {type(value).__name__} as a clock reading")


def clock_now(clock: object | None = None) -> datetime:
    """Read ``clock`` as an aware UTC ``datetime``.

    ``clock`` may be ``None`` (wall clock), a fixed ``datetime`` / ISO string /
    epoch number, an object exposing ``now()``, ``utcnow()``, ``current`` or
    ``time()``, or a plain callable returning any of those readings.
    """
    if clock is None:
        return datetime.now(timezone.utc)
    if isinstance(clock, (datetime, str, int, float)) and not isinstance(clock, bool):
        return _coerce_datetime(clock)
    for attr in ("now", "utcnow", "current", "time"):
        member = getattr(clock, attr, None)
        if member is not None:
            return _coerce_datetime(member() if callable(member) else member)
    if callable(clock):
        return _coerce_datetime(clock())
    raise TypeError(
        f"clock {type(clock).__name__} must expose now()/utcnow()/current/time() or be callable"
    )


# --------------------------------------------------------------------------- disk


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Replace ``path`` with ``data`` atomically, or raise and leave ``path`` untouched.

    The bytes go to a temporary file in the same directory, are fsynced, then
    ``os.replace`` swaps them in.  Any failure (ENOSPC included) propagates as
    the original ``OSError`` after the temporary file is removed; the previous
    contents of ``path`` are never truncated or partially overwritten.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def _dumps(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, sort_keys=True, indent=1) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- sink


class DegradeSink:
    """Bounded, durable, append-style warning sink backed by one JSON file."""

    def __init__(
        self,
        path: Path | str,
        clock: object | None = None,
        max_records: int = MAX_RECORDS,
    ) -> None:
        if int(max_records) < 1:
            raise ValueError("max_records must be >= 1")
        self.path = Path(path)
        self.clock = clock
        self.max_records = int(max_records)

    def __repr__(self) -> str:
        return f"DegradeSink({str(self.path)!r}, max_records={self.max_records})"

    # -- reading (always from disk) ------------------------------------------

    def _empty_doc(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "max_records": self.max_records,
            "next_seq": 1,
            "records": [],
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty_doc()
        raw = self.path.read_bytes()
        if not raw.strip():
            raise DegradeSinkCorrupt(f"{self.path}: empty sink file (torn write?)")
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DegradeSinkCorrupt(f"{self.path}: {exc}") from exc
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            raise DegradeSinkCorrupt(f"{self.path}: not a {SCHEMA} document")
        records = doc.get("records")
        if not isinstance(records, list) or not all(
            isinstance(r, dict) and isinstance(r.get("code"), str) for r in records
        ):
            raise DegradeSinkCorrupt(f"{self.path}: records must be a list of coded objects")
        next_seq = doc.get("next_seq")
        if not isinstance(next_seq, int) or isinstance(next_seq, bool) or next_seq < 1:
            raise DegradeSinkCorrupt(f"{self.path}: next_seq must be a positive integer")
        return doc

    def records(self) -> list[dict[str, Any]]:
        """All retained warning records, oldest first, read fresh from disk."""
        return list(self._read()["records"])

    def count(self, code: str | None = None) -> int:
        """Number of retained records, optionally only those with ``code``."""
        return sum(1 for r in self.records() if code is None or r.get("code") == code)

    def has(self, code: str) -> bool:
        """True when at least one retained record carries ``code``."""
        return any(r.get("code") == code for r in self.records())

    def has_stale(self) -> bool:
        """True when a STALE warning has been durably recorded on this path."""
        return self.has(STALE)

    def dropped_total(self) -> int:
        """How many records were evicted by the bound over the sink's lifetime."""
        return int(self._read().get("dropped_total", 0))

    # -- writing (atomic) -----------------------------------------------------

    def warn(self, code: str, reason: str, **detail: Any) -> dict[str, Any]:
        """Durably record a warning and return the stored record.

        ``code`` is an upper-case identifier such as ``STALE``; ``reason`` is
        free text.  Extra keyword fields are stored under ``detail`` and must
        be JSON-serialisable.  Raises ``OSError`` (loudly) if the record cannot
        be made durable; the previous file is left intact in that case.
        """
        if not isinstance(code, str) or not _CODE_RE.match(code):
            raise ValueError(f"warning code must match {_CODE_RE.pattern}: {code!r}")
        if not isinstance(reason, str):
            raise TypeError("reason must be a string")
        doc = self._read()
        record: dict[str, Any] = {
            "seq": int(doc["next_seq"]),
            "code": code,
            "reason": reason,
            "at": iso_utc(clock_now(self.clock)),
        }
        if detail:
            record["detail"] = detail
        records = list(doc["records"]) + [record]
        dropped = max(0, len(records) - self.max_records)
        new_doc: dict[str, Any] = {
            "schema": SCHEMA,
            "max_records": self.max_records,
            "next_seq": record["seq"] + 1,
            "records": records[dropped:],
        }
        total_dropped = int(doc.get("dropped_total", 0)) + dropped
        if total_dropped:
            new_doc["dropped_total"] = total_dropped
        atomic_write_bytes(self.path, _dumps(new_doc))
        return record

    def warn_stale(self, reason: str) -> dict[str, Any]:
        """Record that a decision was served from a list that is not provably fresh."""
        return self.warn(STALE, reason)

    def clear(self) -> None:
        """Owner action: reset the sink (records are dropped, the sequence restarts)."""
        atomic_write_bytes(self.path, _dumps(self._empty_doc()))
