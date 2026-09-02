#!/usr/bin/env python3
"""Named probe 1: changing one input hash flips the stored verdict to STALE.

Negative control in the same run: a twin record whose inputs are untouched
stays VALID. Hash comparison does not consult the clock.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.freshness import (  # noqa: E402
    HASH_STALE,
    STALE,
    VALID,
    age_invalidated,
    evaluate_freshness,
    hash_inputs,
    hash_invalidated,
    stamp_verdict,
    surface_result,
)

T0 = 1_700_000_000.0
WINDOW = 3600.0
INPUTS = {
    "conformance_pass_rate": 1.0,
    "tests_present": True,
    "tests_pass_rate": 1.0,
    "docs_complete": True,
    "sbom_present": True,
    "provenance_present": True,
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0095-probe1 {msg}")
    return 1


def main() -> int:
    stored = stamp_verdict(
        kind="quality_score",
        subject="fixture.pkg@1.0.0",
        result="PASS",
        inputs=INPUTS,
        computed_at=T0,
        freshness_window_s=WINDOW,
    )
    control = stamp_verdict(
        kind="quality_score",
        subject="fixture.pkg@1.0.0-control",
        result="PASS",
        inputs=INPUTS,
        computed_at=T0,
        freshness_window_s=WINDOW,
    )
    mutated = dict(INPUTS)
    mutated["sbom_present"] = False
    now = T0 + 30

    if hash_inputs(mutated) == stored["input_hashes"]:
        return fail("mutated inputs produced the same hash set")
    if not hash_invalidated(stored, mutated):
        return fail("hash signal silent after one input change")
    if age_invalidated(stored, now):
        return fail("age signal fired inside the window (signals mixed)")

    ev = evaluate_freshness(stored, mutated, now)
    if ev["freshness"] != STALE or ev["hash_signal"] != STALE:
        return fail(f"combined verdict not STALE via hash: {ev}")
    if ev["age_signal"] != VALID or HASH_STALE not in ev["reasons"]:
        return fail(f"hash/age independence broken: {ev}")
    if surface_result(stored, mutated, now) != STALE:
        return fail("surface still showed PASS after input change")

    ctrl = evaluate_freshness(control, INPUTS, now)
    if ctrl["freshness"] != VALID or ctrl["reasons"]:
        return fail(f"negative control flipped: {ctrl}")
    if surface_result(control, INPUTS, now) != "PASS":
        return fail("negative control surface was not PASS")
    if hash_invalidated(control, INPUTS):
        return fail("negative control hash signal fired on unchanged inputs")

    payload = {
        "probe": "probe1-input-hash",
        "unit_id": "IMP-0095",
        "changed_input": "sbom_present",
        "stored_hashes": stored["input_hashes"],
        "mutated_hashes": hash_inputs(mutated),
        "hash_signal": ev["hash_signal"],
        "age_signal": ev["age_signal"],
        "mutated_freshness": ev["freshness"],
        "control_freshness": ctrl["freshness"],
        "surface_after_change": surface_result(stored, mutated, now),
        "negative_control_valid": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "hash_stale=True control_valid=True age_silent=True "
        f"changed={payload['changed_input']}"
    )
    print("SUCCESS:IMP-0095-probe1 input-hash invalidation and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
