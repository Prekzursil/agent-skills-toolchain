"""Freshness semantics for stored quality scores, verdicts and conformance results.

Recovered 2026-10-25 by builder shard 11 wave 2 (IMP-0095) from the delivery
receipt `command-center/receipts/IMP-0095.json`: the original module source was
truncated on the host and only its recorded probe outputs, test roster and
hash scheme survived. The API below is the receipt-pinned contract:

  * a stored score/verdict carries `computed_at` + per-input sha256 hashes
  * changing any hashable input flips the stored verdict to STALE
    (hash signal — never inspects the clock)
  * age beyond the freshness window flips it to STALE
    (age signal — never inspects the hashes); the advisory database is a
    live, unhashable input and is listed, not hashed
  * STALE is never rendered as PASS on any surface, summary included
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

STALE = "STALE"
VALID = "VALID"

HASH_STALE = "HASH_STALE"
AGE_STALE = "AGE_STALE"

#: Live inputs that cannot be hashed (queried live at recompute time).
UNHASHABLE_INPUTS: frozenset[str] = frozenset({"advisory_db"})

DEFAULT_FRESHNESS_WINDOW = timedelta(days=30)


class Clock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        self._now = self._now + delta
        return self._now


def input_digest(value: Any) -> str:
    """sha256 over the canonical JSON encoding of one scalar input."""
    return hashlib.sha256(json.dumps(value).encode("utf-8")).hexdigest()


def hash_inputs(inputs: dict[str, Any]) -> dict[str, str]:
    """Hash every hashable input; unhashable live inputs are listed, not hashed."""
    out: dict[str, str] = {}
    for key in sorted(inputs):
        if key in UNHASHABLE_INPUTS:
            continue
        out[key] = input_digest(inputs[key])
    return out


@dataclass
class VerdictRecord:
    kind: str  # quality_score | vulnerability_verdict | conformance_result
    result: Any
    subject: str = ""
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    input_hashes: dict[str, str] = field(default_factory=dict)
    unhashable_inputs: list[str] = field(default_factory=list)
    freshness_window: timedelta = DEFAULT_FRESHNESS_WINDOW
    freshness: str = VALID
    reasons: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "result": self.result,
            "subject": self.subject,
            "computed_at": self.computed_at.isoformat(),
            "input_hashes": dict(self.input_hashes),
            "unhashable_inputs": list(self.unhashable_inputs),
            "freshness_window_seconds": int(self.freshness_window.total_seconds()),
            "freshness": self.freshness,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_record(cls, data: dict[str, Any]) -> "VerdictRecord":
        return cls(
            kind=str(data.get("kind") or "quality_score"),
            result=data.get("result"),
            subject=str(data.get("subject") or ""),
            computed_at=datetime.fromisoformat(str(data.get("computed_at"))),
            input_hashes=dict(data.get("input_hashes") or {}),
            unhashable_inputs=list(data.get("unhashable_inputs") or []),
            freshness_window=timedelta(
                seconds=int(
                    data.get(
                        "freshness_window_seconds",
                        int(DEFAULT_FRESHNESS_WINDOW.total_seconds()),
                    )
                )
            ),
            freshness=str(data.get("freshness") or VALID),
            reasons=list(data.get("reasons") or []),
        )


def stamp_verdict(
    kind: str,
    result: Any,
    inputs: dict[str, Any],
    clock: Clock | None = None,
    subject: str = "",
    freshness_window: timedelta | None = None,
) -> VerdictRecord:
    """Stamp a fresh verdict: freeze the clock reading and hash the inputs."""
    now = (clock or Clock()).now()
    unhashable = sorted(k for k in inputs if k in UNHASHABLE_INPUTS)
    return VerdictRecord(
        kind=kind,
        result=result,
        subject=subject,
        computed_at=now,
        input_hashes=hash_inputs(inputs),
        unhashable_inputs=unhashable,
        freshness_window=freshness_window or DEFAULT_FRESHNESS_WINDOW,
        freshness=VALID,
    )


def hash_invalidated(record: VerdictRecord, current_inputs: dict[str, Any]) -> bool:
    """True when any hashable input changed or its stored hash is missing.

    Never inspects the clock: the hash and age signals are independent.
    """
    current = hash_inputs(current_inputs)
    for key in sorted(current):
        if record.input_hashes.get(key) != current[key]:
            return True
    # A stored hash with no current counterpart is also a mismatch
    # (the input disappeared), except unhashable inputs which are never stored.
    for key in sorted(record.input_hashes):
        if key not in current:
            return True
    return False


def age_invalidated(record: VerdictRecord, clock: Clock | None = None) -> bool:
    """True when the record is older than its freshness window.

    Never inspects the input hashes.
    """
    now = (clock or Clock()).now()
    return (now - record.computed_at) > record.freshness_window


def evaluate_freshness(
    record: VerdictRecord,
    current_inputs: dict[str, Any] | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Combine both signals; either alone is sufficient to mark STALE."""
    reasons: list[str] = []
    hash_signal = VALID
    age_signal = VALID
    if current_inputs is not None and hash_invalidated(record, current_inputs):
        hash_signal = STALE
        reasons.append(HASH_STALE)
    if age_invalidated(record, clock):
        age_signal = STALE
        reasons.append(AGE_STALE)
    freshness = STALE if (hash_signal == STALE or age_signal == STALE) else VALID
    return {
        "freshness": freshness,
        "hash_signal": hash_signal,
        "age_signal": age_signal,
        "reasons": reasons,
    }


def recompute_if_stale(
    record: VerdictRecord,
    current_inputs: dict[str, Any],
    recompute: "callable[[dict[str, Any]], Any]",
    clock: Clock | None = None,
    kind: str | None = None,
) -> tuple[VerdictRecord, bool]:
    """Recompute only when a signal says the stored verdict is dead.

    Returns (record, recomputed). A VALID record is returned untouched.
    """
    state = evaluate_freshness(record, current_inputs, clock)
    if state["freshness"] == VALID:
        return record, False
    fresh = stamp_verdict(
        kind or record.kind,
        recompute(current_inputs),
        current_inputs,
        clock=clock,
        subject=record.subject,
        freshness_window=record.freshness_window,
    )
    return fresh, True


def age_sweep(
    records: list[VerdictRecord], clock: Clock | None = None
) -> dict[str, Any]:
    """Independently mark every record older than its window as STALE.

    Inspects only ages — never input hashes — so a verdict computed against a
    live advisory database decays even though its recorded inputs never moved.
    """
    swept: list[str] = []
    for record in records:
        if age_invalidated(record, clock):
            record.freshness = STALE
            if AGE_STALE not in record.reasons:
                record.reasons.append(AGE_STALE)
            swept.append(record.subject)
    return {"swept": swept, "count": len(swept)}


# ---------------------------------------------------------------------------
# Surfaces: STALE must never be rendered as PASS anywhere.
# ---------------------------------------------------------------------------

SURFACES: tuple[str, ...] = (
    "surface_result.result_shown",
    "render_record.result_shown",
    "render_api.verdict",
    "summary_view.pass",
)


def enumerate_surfaces() -> list[dict[str, str]]:
    return [{"surface": s, "rule": "STALE never renders as PASS"} for s in SURFACES]


def _shown(record: VerdictRecord) -> str:
    if record.freshness == STALE:
        return STALE
    return str(record.result)


def surface_result(record: VerdictRecord) -> dict[str, Any]:
    shown = _shown(record)
    return {"result_shown": shown, "pass": shown != STALE and bool(record.result)}


def render_record(record: VerdictRecord) -> dict[str, Any]:
    shown = _shown(record)
    return {
        "result_shown": shown,
        "pass": shown != STALE and bool(record.result),
        "freshness": record.freshness,
    }


def render_api(record: VerdictRecord) -> dict[str, Any]:
    return {"verdict": _shown(record)}


def summary_view(records: list[VerdictRecord]) -> dict[str, Any]:
    """Cohort roll-up: only fresh CLEAN records count toward `pass`."""
    passed = sum(1 for r in records if _shown(r) != STALE and bool(r.result))
    stale = sum(1 for r in records if r.freshness == STALE)
    return {
        "total": len(records),
        "pass": passed,
        "stale": stale,
        "stale_never_pass": True,
    }


__all__ = [
    "AGE_STALE",
    "DEFAULT_FRESHNESS_WINDOW",
    "HASH_STALE",
    "STALE",
    "UNHASHABLE_INPUTS",
    "VALID",
    "Clock",
    "VerdictRecord",
    "age_invalidated",
    "age_sweep",
    "enumerate_surfaces",
    "evaluate_freshness",
    "hash_inputs",
    "hash_invalidated",
    "input_digest",
    "recompute_if_stale",
    "render_api",
    "render_record",
    "stamp_verdict",
    "summary_view",
    "surface_result",
]
