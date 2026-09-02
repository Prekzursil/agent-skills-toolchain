#!/usr/bin/env python3
"""Named probe 1: 24-case tally matrix vs hand-computed expected values.

Signal 1: live tally_motion outcomes match expected_matrix.json (authored by
hand, not generated from the engine). Signal 2: every decision artifact carries
the abstention_policy_id that produced its arithmetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from load import load_tally  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0302.json"
EXPECTED_PATH = HERE / "expected_matrix.json"
THRESHOLDS = {"majority", "supermajority", "unanimity"}
POLICIES = {
    "exclude_from_denominator",
    "include_in_denominator",
    "count_as_no",
    "park_on_any_abstention",
}
QUORUMS = {4, 7}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0302-probe1 {msg}")
    return 1


def main() -> int:
    if not EXPECTED_PATH.is_file():
        return fail("expected_matrix.json missing")
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    cases = expected.get("cases") or []
    if len(cases) != 24:
        return fail(f"expected 24 cases, got {len(cases)}")

    combos = {
        (c["threshold_id"], c["abstention_policy_id"], c["quorum_required"])
        for c in cases
    }
    want = {(t, p, q) for t in THRESHOLDS for p in POLICIES for q in QUORUMS}
    if combos != want:
        missing = sorted(want - combos)
        extra = sorted(combos - want)
        return fail(f"matrix not a full 3x4x2 product missing={missing} extra={extra}")

    tally = load_tally()
    ballots = expected["ballots"]
    mismatches = []
    missing_policy = []
    for case in cases:
        art = tally.tally_motion(
            ballots,
            threshold_id=case["threshold_id"],
            abstention_policy_id=case["abstention_policy_id"],
            quorum_required=case["quorum_required"],
            seated=expected["seated"],
            motion_id=case["case_id"],
        )
        if art.get("abstention_policy_id") != case["abstention_policy_id"]:
            missing_policy.append(case["case_id"])
        if art.get("policy_recorded") is not True:
            missing_policy.append(case["case_id"])
        got = {
            "outcome": art.get("outcome"),
            "yes": art.get("yes"),
            "denominator": art.get("denominator")
            if case.get("expected_denominator") is not None
            else None,
        }
        exp = {
            "outcome": case["expected_outcome"],
            "yes": case["expected_yes"],
            "denominator": case.get("expected_denominator"),
        }
        if case.get("expected_effective_no") is not None:
            got["effective_no"] = art.get("effective_no")
            exp["effective_no"] = case["expected_effective_no"]
        if case.get("hand_ratio") and case["expected_outcome"] not in {
            "PARKED",
            "NO_QUORUM",
        }:
            got["ratio"] = art.get("ratio")
            exp["ratio"] = case["hand_ratio"]
        if got != exp:
            mismatches.append({"case_id": case["case_id"], "expected": exp, "got": got})

    if missing_policy:
        return fail(f"policy id absent on {missing_policy}")
    if mismatches:
        print(json.dumps(mismatches, indent=2)[:4000])
        return fail(f"{len(mismatches)} matrix mismatches")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("catalog receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(receipt)
    if receipt.get("unit_id") != "IMP-0302":
        return fail(f"receipt unit_id={receipt.get('unit_id')}")
    if "SUCCESS:IMP-0302" not in text:
        return fail("sentinel absent from receipt")
    matrix = receipt.get("tally_matrix") or {}
    rows = matrix.get("rows") or receipt.get("tally_matrix_rows") or []
    if len(rows) != 24:
        return fail(f"receipt matrix rows={len(rows)} want=24")

    print(
        json.dumps(
            {
                "probe": "probe1-tally-matrix",
                "unit_id": "IMP-0302",
                "cases": 24,
                "mismatches": 0,
                "policy_recorded_on_all": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("cases=24 mismatches=0 policy_recorded=True")
    print("SUCCESS:IMP-0302-probe1 24-case tally matrix and recorded policy id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
