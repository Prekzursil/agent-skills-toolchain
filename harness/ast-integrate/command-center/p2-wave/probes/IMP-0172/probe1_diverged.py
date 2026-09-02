#!/usr/bin/env python3
"""Probe 1: both-sides-unique fixture is DIVERGED, not one-sided.

Catalog tests_required[0] and evidence signal (1). The one-directional mutant
(the measured 31-misclassification shape) must NOT report DIVERGED. Both-states:
strip the left-unique stage and the two-directional verdict must leave DIVERGED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import semantic_diff as D  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0172.json"


def main() -> int:
    left = F.both_sides_left()
    right = F.both_sides_right()
    two = D.diff_workflows(left, right)
    one = D.diff_workflows(left, right, one_directional=True)
    print(
        json.dumps(
            {
                "probe": "probe1-diverged",
                "unit_id": "IMP-0172",
                "two_directional_verdict": two["verdict"],
                "one_directional_verdict": one["verdict"],
                "left_unique": len(two["left_unique"]),
                "right_unique": len(two["right_unique"]),
                "ops": [o["op"] for o in two["ops"]],
            },
            sort_keys=True,
        )
    )
    if two["verdict"] != "DIVERGED":
        print(f"FAILED:IMP-0172-probe1 both-sides-unique verdict={two['verdict']} want=DIVERGED")
        return 1
    if not two["left_unique"] or not two["right_unique"]:
        print("FAILED:IMP-0172-probe1 unique sets did not both fire")
        return 1
    if "removed_stage" not in {o["op"] for o in two["ops"]}:
        print("FAILED:IMP-0172-probe1 missing removed_stage (left unique stage)")
        return 1
    if "added_stage" not in {o["op"] for o in two["ops"]}:
        print("FAILED:IMP-0172-probe1 missing added_stage (right unique stage)")
        return 1
    if one["verdict"] == "DIVERGED":
        print("FAILED:IMP-0172-probe1 one-directional mutant also said DIVERGED")
        return 1
    if one["verdict"] != "RIGHT-AHEAD":
        print(
            f"FAILED:IMP-0172-probe1 one-directional verdict={one['verdict']} "
            "want=RIGHT-AHEAD (the measured blind spot)"
        )
        return 1

    stripped = D.diff_workflows(F._base(), right)
    print(f"both_states_stripped_left verdict={stripped['verdict']}")
    if stripped["verdict"] == "DIVERGED":
        print("FAILED:IMP-0172-probe1 both-states: stripping left unique still DIVERGED")
        return 1
    if stripped["verdict"] != "RIGHT-AHEAD":
        print(
            f"FAILED:IMP-0172-probe1 both-states stripped verdict={stripped['verdict']} "
            "want=RIGHT-AHEAD"
        )
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0172" not in text:
            print("FAILED:IMP-0172-probe1 receipt sentinel absent")
            return 1
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0172-probe1 receipt self-declared {st}")
            return 1
        if doc.get("both_sides_unique_verdict") not in (None, "DIVERGED"):
            if doc.get("both_sides_unique_verdict") != "DIVERGED":
                print("FAILED:IMP-0172-probe1 receipt both_sides_unique_verdict drifted")
                return 1

    print("SUCCESS:IMP-0172-probe1 both-sides-unique classified DIVERGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
