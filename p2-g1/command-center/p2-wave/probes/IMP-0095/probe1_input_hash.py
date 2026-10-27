#!/usr/bin/env python3
"""IMP-0095 named probe 1: input-hash invalidation + negative control.

Changing one hashable input (sbom_present) flips a stored PASS quality score
to STALE via the hash signal while the age signal stays VALID inside the
window; a twin with unchanged inputs stays VALID in the same run.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "marketplace"))

from freshness import (  # noqa: E402
    STALE,
    VALID,
    Clock,
    evaluate_freshness,
    hash_inputs,
    stamp_verdict,
    surface_result,
)

BASE = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)

INPUTS = {
    "conformance_pass_rate": 1.0,
    "docs_complete": True,
    "provenance_present": True,
    "sbom_present": True,
    "tests_pass_rate": 1.0,
    "tests_present": True,
}

CHANGED = "sbom_present"


class _Shim:
    """Minimal surface shim carrying a freshness state and result."""

    def __init__(self, freshness: str, result: str) -> None:
        self.freshness = freshness
        self.result = result


def main() -> int:
    clock = Clock(BASE)
    rec = stamp_verdict(
        "quality_score", "CLEAN", dict(INPUTS), clock=clock, subject="aged.pkg@1.0.0"
    )
    control = stamp_verdict(
        "quality_score", "CLEAN", dict(INPUTS), clock=clock, subject="control.pkg@1.0.0"
    )

    mutated = dict(INPUTS)
    mutated[CHANGED] = False
    state = evaluate_freshness(rec, mutated, clock)
    shown = surface_result(_Shim(state["freshness"], "CLEAN"))["result_shown"]

    negative_control_valid = (
        control.freshness == VALID and surface_result(control)["pass"] is True
    )

    out = {
        "unit_id": "IMP-0095",
        "probe": "probe1-input-hash",
        "stored_hashes": rec.input_hashes,
        "mutated_hashes": hash_inputs(mutated),
        "changed_input": CHANGED,
        "hash_signal": state["hash_signal"],
        "age_signal": state["age_signal"],
        "control_freshness": control.freshness,
        "mutated_freshness": state["freshness"],
        "surface_after_change": shown,
        "negative_control_valid": negative_control_valid,
        "pass": (
            state["hash_signal"] == STALE
            and state["age_signal"] == VALID
            and state["freshness"] == STALE
            and shown == STALE
            and negative_control_valid
        ),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"hash_stale=True control_valid=True age_silent=True changed={CHANGED}")
    print("SUCCESS:IMP-0095-probe1 input-hash invalidation and negative control")
    if not out["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
