"""Two-signal hang detector: heartbeat token AND output byte growth.

A unit is STALLED only when BOTH signals have been flat for ``stall_window_s``:
its heartbeat token stopped advancing AND its output stopped changing size.
A slow-but-alive unit keeps at least one signal moving and is never stalled.
Classifying from a single signal is refused (``UNDECIDABLE``), and mtime is
rejected outright (``MtimeRejected``) because a live-but-quiet unit has the
same mtime profile as a hung one. A live unit that outlasts ``timeout_s`` is
TIMEOUT, which -- like STALLED -- releases its scheduler slot.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

STALLED = "STALLED"
ALIVE = "ALIVE"
TIMEOUT = "TIMEOUT"
UNDECIDABLE = "UNDECIDABLE"

HEARTBEAT = "heartbeat"
BYTES = "bytes"
SIGNALS: tuple[str, ...] = (HEARTBEAT, BYTES)
MIN_SIGNALS = 2
DEFAULT_TIMEOUT_SECONDS = 2700


class MtimeRejected(ValueError):
    """mtime (or anything derived from it) is not admissible as a signal."""


@dataclass
class Verdict:
    """Outcome of one hang classification."""

    state: str
    heartbeat_advanced: bool = False
    byte_growth: bool = False
    slot_released: bool = False
    time_to_classification_s: float | None = None
    unit_id: str = ""
    samples: int = 0
    signals: tuple[str, ...] = SIGNALS
    reason: str = ""
    stall_window_s: float | None = None
    timeout_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "heartbeat_advanced": self.heartbeat_advanced,
            "byte_growth": self.byte_growth,
            "slot_released": self.slot_released,
            "time_to_classification_s": self.time_to_classification_s,
            "unit_id": self.unit_id,
            "samples": self.samples,
            "signals": list(self.signals),
            "reason": self.reason,
            "stall_window_s": self.stall_window_s,
            "timeout_s": self.timeout_s,
        }


class SlotTracker:
    """Occupancy of scheduler slots; a STALLED/TIMEOUT verdict frees its slot."""

    def __init__(self, capacity: int = 1) -> None:
        self.capacity = int(capacity)
        if self.capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._held: set[str] = set()

    def acquire(self, unit_id: str) -> None:
        if len(self._held) >= self.capacity and str(unit_id) not in self._held:
            raise RuntimeError(f"no free slot (capacity {self.capacity}) for {unit_id!r}")
        self._held.add(str(unit_id))

    def release(self, unit_id: str) -> bool:
        before = len(self._held)
        self._held.discard(str(unit_id))
        return len(self._held) < before

    def occupied_count(self) -> int:
        return len(self._held)

    def holders(self) -> list[str]:
        return sorted(self._held)


def catalog_timeout_seconds(catalog: Path, unit_id: str) -> int:
    """Per-unit timeout from the work-unit catalog (catalog default otherwise)."""
    try:
        data = json.loads(Path(catalog).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_TIMEOUT_SECONDS
    default = data.get("defaults", {}).get("timeout_seconds") if isinstance(data, dict) else None
    fallback = int(default) if isinstance(default, (int, float)) else DEFAULT_TIMEOUT_SECONDS
    units = data.get("work_units") if isinstance(data, dict) else None
    for unit in units or []:
        if not isinstance(unit, dict) or unit.get("id") != unit_id:
            continue
        raw = unit.get("timeout_seconds")
        if raw is None:
            timeout = unit.get("timeout")
            raw = timeout.get("seconds") if isinstance(timeout, dict) else timeout
        if raw is None:
            return fallback
        return int(raw)
    return fallback


def reject_mtime(extra: Mapping[str, Any] | None) -> None:
    """Refuse any extra observation that carries mtime under any spelling."""
    if not extra:
        return
    for key in extra:
        if "mtime" in str(key).lower():
            raise MtimeRejected(
                f"{key!r} is not admissible: mtime cannot distinguish a slow unit "
                "from a hung one"
            )


def _token(path: Path) -> int:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return int(doc.get("token") or 0)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return 0


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


class _StallTracker:
    """Incremental two-signal stall detection over (t, token, bytes) samples."""

    def __init__(self, signals: Sequence[str], stall_window_s: float) -> None:
        self.signals = tuple(signals)
        self.window = float(stall_window_s)
        self.prev_tok: int | None = None
        self.prev_sz: int | None = None
        self.last_change = {HEARTBEAT: 0.0, BYTES: 0.0}
        self.hb_adv = False
        self.byte_adv = False
        self.count = 0

    def feed(self, t: float, token: int, size: int) -> bool:
        """Record one sample; True once every tracked signal is flat for the window."""
        self.count += 1
        if self.prev_tok is None:
            self.prev_tok, self.prev_sz = token, size
        if token != self.prev_tok:
            self.hb_adv = True
            self.last_change[HEARTBEAT] = t
            self.prev_tok = token
        if size != self.prev_sz:
            self.byte_adv = True
            self.last_change[BYTES] = t
            self.prev_sz = size
        if t < self.window:
            return False
        return all((t - self.last_change[s]) >= self.window for s in self.signals)


def _validated_signals(signals: Iterable[str]) -> tuple[str, ...]:
    sig = tuple(dict.fromkeys(str(s) for s in signals))
    unknown = [s for s in sig if s not in SIGNALS]
    if unknown:
        raise ValueError(f"unknown signals {unknown}; admissible: {list(SIGNALS)}")
    if not sig:
        raise ValueError("at least one signal is required")
    return sig


def _classify_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    signals: tuple[str, ...],
    timeout_s: float,
    stall_window_s: float,
    unit_id: str,
    enforce_cardinality: bool,
) -> Verdict:
    tracker = _StallTracker(signals, stall_window_s)
    last_t = 0.0
    for sample in samples:
        t = float(sample.get("t", 0.0))
        last_t = max(last_t, t)
        stalled = tracker.feed(t, int(sample.get("token", 0)), int(sample.get("bytes", 0)))
        if stalled and (len(signals) >= MIN_SIGNALS or not enforce_cardinality):
            return Verdict(
                state=STALLED,
                heartbeat_advanced=tracker.hb_adv,
                byte_growth=tracker.byte_adv,
                time_to_classification_s=t,
                unit_id=unit_id,
                samples=tracker.count,
                signals=signals,
                reason="all tracked signals flat for the stall window",
                stall_window_s=float(stall_window_s),
                timeout_s=float(timeout_s),
            )
    common = dict(
        heartbeat_advanced=tracker.hb_adv,
        byte_growth=tracker.byte_adv,
        time_to_classification_s=last_t if samples else None,
        unit_id=unit_id,
        samples=tracker.count,
        signals=signals,
        stall_window_s=float(stall_window_s),
        timeout_s=float(timeout_s),
    )
    if enforce_cardinality and len(signals) < MIN_SIGNALS:
        return Verdict(
            state=UNDECIDABLE,
            reason=f"{len(signals)} signal(s) cannot prove a stall; need {MIN_SIGNALS}",
            **common,
        )
    if samples and last_t >= float(timeout_s):
        return Verdict(state=TIMEOUT, reason="hard timeout reached", **common)
    if tracker.hb_adv or tracker.byte_adv:
        return Verdict(state=ALIVE, reason="a signal advanced within the window", **common)
    return Verdict(state=UNDECIDABLE, reason="no signal moved and no stall window elapsed", **common)


def classify(
    samples: Sequence[Mapping[str, Any]],
    *,
    timeout_s: float,
    stall_window_s: float,
    signals: Iterable[str] = SIGNALS,
    extra: Mapping[str, Any] | None = None,
    unit_id: str = "unit",
) -> Verdict:
    """Production classifier over recorded samples.

    STALLED needs both signals flat for the window; asking for fewer than
    ``MIN_SIGNALS`` yields UNDECIDABLE, never STALLED. ``extra`` observations
    naming mtime raise ``MtimeRejected``.
    """
    reject_mtime(extra)
    sig = _validated_signals(signals)
    return _classify_samples(
        list(samples),
        signals=sig,
        timeout_s=timeout_s,
        stall_window_s=stall_window_s,
        unit_id=unit_id,
        enforce_cardinality=True,
    )


def classify_heartbeat_only_defective(
    samples: Sequence[Mapping[str, Any]],
    *,
    timeout_s: float,
    stall_window_s: float,
    unit_id: str = "mutant:heartbeat-only",
) -> Verdict:
    """MUTATION CONTROL, not for production: judge the heartbeat alone.

    This is the byte-growth signal removed. It exists so the probes can show
    that dropping the second signal turns a slow-but-alive unit red (STALLED);
    ``classify`` refuses this shape with UNDECIDABLE.
    """
    return _classify_samples(
        list(samples),
        signals=(HEARTBEAT,),
        timeout_s=timeout_s,
        stall_window_s=stall_window_s,
        unit_id=unit_id,
        enforce_cardinality=False,
    )


def watch(
    hb: Path,
    out: Path,
    timeout_s: float = 4.0,
    stall_window_s: float = 0.28,
    poll_s: float = 0.05,
    unit_id: str = "unit",
    slot: SlotTracker | None = None,
    confirm_alive_s: float | None = None,
    signals: Iterable[str] = SIGNALS,
    extra: Mapping[str, Any] | None = None,
) -> tuple[Verdict, list[dict[str, Any]]]:
    """Poll a live unit's heartbeat file and output file until classified.

    Returns the verdict and the raw samples so ``classify`` can be re-run over
    them. STALLED and TIMEOUT release the unit's slot; ALIVE (reached after
    ``confirm_alive_s`` with at least one signal moving) keeps it occupied.
    """
    reject_mtime(extra)
    sig = _validated_signals(signals)
    hb, out = Path(hb), Path(out)
    if slot is not None:
        slot.acquire(unit_id)
    tracker = _StallTracker(sig, stall_window_s)
    samples: list[dict[str, Any]] = []
    start = time.monotonic()
    deadline = start + float(timeout_s)
    alive_deadline = start + float(confirm_alive_s) if confirm_alive_s else None

    def finish(state: str, t: float, reason: str, release: bool) -> Verdict:
        verdict = Verdict(
            state=state,
            heartbeat_advanced=tracker.hb_adv,
            byte_growth=tracker.byte_adv,
            time_to_classification_s=t,
            unit_id=unit_id,
            samples=len(samples),
            signals=sig,
            reason=reason,
            stall_window_s=float(stall_window_s),
            timeout_s=float(timeout_s),
        )
        if release and slot is not None:
            slot.release(unit_id)
            verdict.slot_released = True
        return verdict

    while True:
        now = time.monotonic()
        t = now - start
        tok = _token(hb)
        sz = _size(out)
        samples.append({"t": t, "token": tok, "bytes": sz})
        stalled = tracker.feed(t, tok, sz)
        if stalled and len(sig) >= MIN_SIGNALS:
            return finish(STALLED, t, "all tracked signals flat for the stall window", True), samples
        if alive_deadline is not None and now >= alive_deadline and (tracker.hb_adv or tracker.byte_adv):
            return finish(ALIVE, t, "a signal advanced within the confirmation window", False), samples
        if now >= deadline:
            if len(sig) < MIN_SIGNALS and stalled:
                return finish(UNDECIDABLE, t, "single signal flat; cannot prove a stall", True), samples
            return finish(TIMEOUT, t, "hard timeout reached", True), samples
        time.sleep(poll_s)
