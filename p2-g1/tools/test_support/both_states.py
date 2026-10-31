"""VALID iff a detector is silent on known-good and fires on known-broken."""
from __future__ import annotations

from typing import Any, Callable

FIRES = "FIRES"
SILENT = "SILENT"


class BothStatesError(Exception):
    def __init__(self, reason: str, record: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.record = record or {}


def _observe(detector: Callable[[Any], Any], state: Any) -> dict[str, Any]:
    fired = bool(detector(state))
    return {
        "fired": fired,
        "observation": FIRES if fired else SILENT,
        "state_label": (state.get("label") if isinstance(state, dict) else None),
    }


def run_both_states(
    detector: Callable[[Any], Any],
    known_good: Any,
    known_broken: Any,
    *,
    detector_id: str = "",
) -> dict[str, Any]:
    good = _observe(detector, known_good)
    bad = _observe(detector, known_broken)
    silent_good = good["observation"] == SILENT
    fires_bad = bad["observation"] == FIRES
    if silent_good and fires_bad:
        reason = "silent-on-good-then-fires-on-broken"
        valid = True
        verdict = "VALID"
    elif (not silent_good) and fires_bad:
        reason = "fires-in-both"
        valid = False
        verdict = "REJECTED"
    elif silent_good and (not fires_bad):
        reason = "silent-in-both"
        valid = False
        verdict = "REJECTED"
    else:
        reason = "fires-on-good-silent-on-broken"
        valid = False
        verdict = "REJECTED"
    return {
        "detector_id": detector_id,
        "verdict": verdict,
        "reason": reason,
        "valid": valid,
        "known_good": good,
        "known_broken": bad,
        "fired_on_bad_state": fires_bad,
        "silent_on_good_state": silent_good,
    }


def assert_both_states(
    detector: Callable[[Any], Any],
    known_good: Any,
    known_broken: Any,
    *,
    detector_id: str = "",
) -> dict[str, Any]:
    rec = run_both_states(
        detector, known_good, known_broken, detector_id=detector_id
    )
    if not rec.get("valid"):
        raise BothStatesError(str(rec.get("reason") or "rejected"), rec)
    return rec
