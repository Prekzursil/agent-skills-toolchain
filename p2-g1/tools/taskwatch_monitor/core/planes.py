"""The two observation planes + BLIND handling (grill S5/S6/S7).

* **Liveness plane** — universal, works for ANY task: does the signal keep
  changing (mtime advancing, bytes/lines growing, process up)? A run that stops
  changing for ``stall_after_s`` is STALLED, not silently "done".

* **Progress plane** — OPTIONAL, driven by a ``progress.json`` heartbeat
  ``{schema, done, total|null, phase, ts, seq}``. The WHOLE record is ingested
  (never a fixed tail) and a **monotonic seq** guard rejects stale/rolled-over
  records so a log-rolloff can never undercount ``done`` (grill S6b).

* **BLIND** — a poll error keeps the last accepted snapshot with an age stamp;
  absence of signal is never rendered as completion (grill S7).

``LivenessMonitor``/``ProgressTracker`` are tiny stateful reducers fed one
sample at a time; every method takes ``now``/``ts`` explicitly so no wall clock
is read and 100% branch coverage is reachable deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import PollResult, ProgressSnapshot

PROGRESS_SCHEMA = "taskwatch.progress/1"


@dataclass
class LivenessSample:
    """The change-detecting signals distilled from one :class:`PollResult`."""

    ts: float
    exists: bool
    mtime: float | None
    size: int | None
    line_count: int

    @classmethod
    def from_poll(cls, ts: float, poll: PollResult) -> "LivenessSample":
        return cls(
            ts=ts,
            exists=poll.exists,
            mtime=poll.mtime,
            size=poll.size,
            line_count=len(poll.lines),
        )


@dataclass
class LivenessVerdict:
    progressing: bool
    stalled: bool
    reason: str
    last_change_ts: float


def _changed(prev: LivenessSample, cur: LivenessSample) -> bool:
    """True if any universal-liveness signal advanced between two samples."""
    if cur.mtime is not None and prev.mtime is not None and cur.mtime > prev.mtime:
        return True
    if cur.size is not None and prev.size is not None and cur.size > prev.size:
        return True
    if cur.line_count > prev.line_count:
        return True
    return cur.exists != prev.exists


class LivenessMonitor:
    """Stateful reducer over :class:`LivenessSample`s producing a verdict."""

    def __init__(self, *, stall_after_s: float) -> None:
        self.stall_after_s = stall_after_s
        self._prev: LivenessSample | None = None
        self._last_change_ts: float = 0.0

    def update(self, sample: LivenessSample) -> LivenessVerdict:
        if self._prev is None:
            self._prev = sample
            self._last_change_ts = sample.ts
            return LivenessVerdict(
                progressing=sample.exists,
                stalled=False,
                reason="first-sample",
                last_change_ts=sample.ts,
            )
        if _changed(self._prev, sample):
            self._prev = sample
            self._last_change_ts = sample.ts
            return LivenessVerdict(
                progressing=True,
                stalled=False,
                reason="changed",
                last_change_ts=sample.ts,
            )
        self._prev = sample
        idle = sample.ts - self._last_change_ts
        if idle >= self.stall_after_s:
            return LivenessVerdict(
                progressing=False,
                stalled=True,
                reason="stalled",
                last_change_ts=self._last_change_ts,
            )
        return LivenessVerdict(
            progressing=False,
            stalled=False,
            reason="idle",
            last_change_ts=self._last_change_ts,
        )


@dataclass
class ProgressResult:
    snapshot: ProgressSnapshot | None
    accepted: bool
    reason: str


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


class ProgressTracker:
    """Ingests progress.json records, enforcing schema + monotonic seq."""

    def __init__(self, *, schema: str = PROGRESS_SCHEMA) -> None:
        self.schema = schema
        self._last_seq: int | None = None
        self._last_snapshot: ProgressSnapshot | None = None

    @property
    def last(self) -> ProgressSnapshot | None:
        return self._last_snapshot

    def ingest(self, record: dict[str, object]) -> ProgressResult:
        schema = record.get("schema")
        if schema != self.schema:
            return ProgressResult(self._last_snapshot, False, "bad-schema")

        seq_raw = record.get("seq")
        if isinstance(seq_raw, bool) or not isinstance(seq_raw, int):
            return ProgressResult(self._last_snapshot, False, "bad-seq")
        if self._last_seq is not None and seq_raw <= self._last_seq:
            # Stale or rolled-over record — keep the higher last-known progress.
            return ProgressResult(self._last_snapshot, False, "stale-seq")

        done = _coerce_float(record.get("done"))
        if done is None:
            return ProgressResult(self._last_snapshot, False, "bad-done")
        ts = _coerce_float(record.get("ts"))
        if ts is None:
            return ProgressResult(self._last_snapshot, False, "bad-ts")

        total = _coerce_float(record.get("total"))  # None ⇒ unknown denominator
        phase = record.get("phase")
        phase_str = phase if isinstance(phase, str) else ""

        snapshot = ProgressSnapshot(
            schema=self.schema,
            done=done,
            total=total,
            phase=phase_str,
            ts=ts,
            seq=seq_raw,
        )
        self._last_seq = seq_raw
        self._last_snapshot = snapshot
        return ProgressResult(snapshot, True, "accepted")


@dataclass
class BlindState:
    """Holds the last good verdict while polls are failing (grill S7)."""

    last_poll: PollResult | None = None
    last_ok_ts: float | None = None
    consecutive_errors: int = 0
    history: list[str] = field(default_factory=list)

    @property
    def blind(self) -> bool:
        return self.consecutive_errors > 0

    def observe(self, ts: float, poll: PollResult) -> None:
        if poll.blind:
            self.consecutive_errors += 1
            self.history.append(poll.error or "error")
        else:
            self.consecutive_errors = 0
            self.last_poll = poll
            self.last_ok_ts = ts

    def age(self, now: float) -> float | None:
        """Seconds since the last non-blind poll, or None if never seen one."""
        if self.last_ok_ts is None:
            return None
        return now - self.last_ok_ts
