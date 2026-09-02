"""Both-states classification for a detector adapter (TST-0018, IMP-0471).

A detector is only credited when it is SILENT on the known-good state and
FIRES on the known-broken state. Everything else is loud: SILENT-BOTH and
IDENTICAL mean the detector measures nothing, ERROR means the adapter or
polarity is broken, NOT-CHECKED means no known-broken fixture exists.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

MEASURES_NOTHING = "MEASURES-NOTHING"
VERDICT_DIFFERS = "DIFFERS"
VERDICT_SILENT_BOTH = "SILENT-BOTH"
VERDICT_IDENTICAL = "IDENTICAL"
VERDICT_NOT_CHECKED = "NOT-CHECKED"
VERDICT_ERROR = "ERROR"


def canonicalize(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


_UNSET: Any = object()


def two_state_valid(good_or_state: Any, broken: Any = _UNSET) -> Any:
    """Two forms share this name.

    ``two_state_valid(good, broken) -> bool``: the two outputs differ once
    canonicalised (the detector measured something).

    ``two_state_valid(state) -> dict``: a known-good control *detector* for
    ``run_two_state``: SILENT on ``"good"``, FIRES on ``"broken"``. The scanner
    plants it beside an inert stub to prove the scan itself is two-stated.
    """
    if broken is _UNSET:
        state = good_or_state
        if state not in ("good", "broken"):
            raise ValueError(f"state must be 'good' or 'broken', got {state!r}")
        return {"fired": state == "broken", "payload": state}
    return canonicalize(good_or_state) != canonicalize(broken)


def inert_stub(_state: str) -> dict[str, Any]:
    return {"fired": False, "payload": "inert"}


@dataclass
class TwoStateRecord:
    detector_id: str
    verdict: str
    valid: bool
    reason: str
    good: Any = None
    broken: Any = None
    has_known_broken_fixture: bool = True

    @property
    def differs(self) -> bool:
        """True only for the credited verdict: silent on good, fires on broken."""
        return self.verdict == VERDICT_DIFFERS

    @property
    def silent_in_both(self) -> bool:
        """True when the detector stayed silent on both states (measures nothing)."""
        return self.verdict == VERDICT_SILENT_BOTH

    @property
    def good_output(self) -> Any:
        return self.good

    @property
    def broken_output(self) -> Any:
        return self.broken

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector_id": self.detector_id,
            "verdict": self.verdict,
            "valid": self.valid,
            "differs": self.differs,
            "silent_in_both": self.silent_in_both,
            "reason": self.reason,
            "good": self.good,
            "broken": self.broken,
            "good_output": self.good,
            "broken_output": self.broken,
            "has_known_broken_fixture": self.has_known_broken_fixture,
        }


def _fired(payload: Any) -> bool:
    if isinstance(payload, dict):
        return bool(payload.get("fired"))
    return bool(payload)


def run_two_state(
    check: Callable[[str], Any] | None,
    *,
    detector_id: str = "",
) -> TwoStateRecord:
    if check is None:
        return TwoStateRecord(
            detector_id=detector_id,
            verdict=VERDICT_NOT_CHECKED,
            valid=False,
            reason="no-known-broken-fixture",
            has_known_broken_fixture=False,
        )
    try:
        good = check("good")
        broken = check("broken")
    except Exception as exc:  # adapter blew up: loud, never silent-pass
        return TwoStateRecord(
            detector_id=detector_id,
            verdict=VERDICT_ERROR,
            valid=False,
            reason=f"adapter-raised {type(exc).__name__}: {exc}",
        )
    if canonicalize(good) == canonicalize(broken):
        verdict = VERDICT_SILENT_BOTH if not _fired(good) else VERDICT_IDENTICAL
        return TwoStateRecord(
            detector_id=detector_id,
            verdict=verdict,
            valid=False,
            reason=MEASURES_NOTHING,
            good=good,
            broken=broken,
        )
    if _fired(good) or not _fired(broken):
        return TwoStateRecord(
            detector_id=detector_id,
            verdict=VERDICT_ERROR,
            valid=False,
            reason="polarity: fired on good or stayed silent on broken",
            good=good,
            broken=broken,
        )
    return TwoStateRecord(
        detector_id=detector_id,
        verdict=VERDICT_DIFFERS,
        valid=True,
        reason="silent-on-good-then-fires-on-broken",
        good=good,
        broken=broken,
    )


def harness_self_test() -> dict[str, Any]:
    """The harness itself is two-stated: valid, inert, always-fire, no-fixture."""
    valid = run_two_state(
        lambda state: {"fired": state == "broken", "payload": state},
        detector_id="harness-valid-control",
    )
    inert = run_two_state(inert_stub, detector_id="harness-inert-stub")
    always = run_two_state(
        lambda _state: {"fired": True, "payload": "constant"},
        detector_id="harness-always-fire",
    )
    missing = run_two_state(None, detector_id="harness-missing-fixture")
    ok = (
        valid.verdict == VERDICT_DIFFERS
        and inert.verdict == VERDICT_SILENT_BOTH
        and always.verdict == VERDICT_IDENTICAL
        and missing.verdict == VERDICT_NOT_CHECKED
    )
    return {
        "pass": ok,
        "two_state_valid": valid.to_dict(),
        "inert_stub": inert.to_dict(),
        "always_fire": always.to_dict(),
        "missing_fixture": missing.to_dict(),
    }


def run(good: Any, broken: Any, fn: Callable[[Any], Any] | None = None) -> dict[str, Any]:
    if fn is None:
        return {"good": good, "broken": broken, "identical": good == broken}
    return run_two_state(lambda state: fn(good if state == "good" else broken)).to_dict()
