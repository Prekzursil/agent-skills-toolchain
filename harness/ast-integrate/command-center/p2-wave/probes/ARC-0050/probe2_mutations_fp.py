#!/usr/bin/env python3
"""Probe 2: per-test guard mutation (red/green) and false-positive budget.

Independent of probe 1's canary plant: re-runs mutations and the clean corpus,
and checks the named hole the reviewer says the suite would not catch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402

ART = REPO / "command-center/phase3/A7/TEST-PLAN.json"


def main() -> int:
    live = S.run_suite()
    mutations = live["mutations"]
    if len(mutations) < 3:
        print("FAILED:ARC-0050-probe2 fewer than 3 mutations")
        return 1
    bad = [
        m
        for m in mutations
        if not m["guard_removed_red"] or not m["guard_restored_green"]
    ]
    if bad:
        print("FAILED:ARC-0050-probe2 mutation did not go red-then-green")
        print(json.dumps(bad, indent=2)[:2000])
        return 1
    fp = live["false_positive_budget"]
    if not fp["within_budget"]:
        print("FAILED:ARC-0050-probe2 false-positive budget exceeded")
        print(json.dumps(fp, indent=2))
        return 1
    hole = live["uncaught_control"]
    if not hole["proves_named_hole"]:
        print("FAILED:ARC-0050-probe2 named hole did not stay silent")
        return 1
    inj = live["injection"]
    if inj["documented_hole"] and inj["documented_hole"].get("caught"):
        print("FAILED:ARC-0050-probe2 documented annotation hole was caught")
        return 1
    if not live["ok"]:
        print("FAILED:ARC-0050-probe2 suite not green")
        return 1

    validator = S.catalog_validator()
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ]
    rejected = 0
    for doc in garbage:
        if list(validator.iter_errors(doc)):
            rejected += 1
    if rejected != 3:
        print("FAILED:ARC-0050-probe2 schema accepted garbage")
        return 1

    if ART.is_file():
        art = json.loads(ART.read_text(encoding="utf-8"))
        report = art.get("report") if isinstance(art.get("report"), dict) else {}
        rec_fp = report.get("false_positive_budget") or art.get("false_positive_budget") or {}
        if rec_fp.get("within_budget") is not True:
            print("FAILED:ARC-0050-probe2 artifact FP budget not within_budget")
            return 1
        rec_mut = report.get("mutations") or art.get("mutations") or []
        if len(rec_mut) < 3:
            print("FAILED:ARC-0050-probe2 artifact mutations missing")
            return 1
        reviewer = art.get("reviewer") or {}
        uncaught = (
            str(reviewer.get("notes") or "")
            + " "
            + str(report.get("reviewer_uncaught") or "")
            + " "
            + str(reviewer.get("mutation_suite_would_not_catch") or "")
        )
        if "arc0050-local-" not in uncaught:
            print("FAILED:ARC-0050-probe2 reviewer hole does not name the local-token miss")
            return 1
        errs = list(validator.iter_errors(art))
        if errs:
            print("FAILED:ARC-0050-probe2 artifact failed schema")
            print(errs[0].message)
            return 1

    out = {
        "probe": "probe2-mutations-fp",
        "unit_id": "ARC-0050",
        "mutations": len(mutations),
        "all_red_to_green": True,
        "fp_rate": fp["measured_rate"],
        "fp_n_clean": fp["n_clean"],
        "named_hole_silent": hole["proves_named_hole"],
        "schema_rejected_garbage": rejected,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"mutations={len(mutations)} red_to_green=True "
        f"fp_rate={fp['measured_rate']} hole_silent=True"
    )
    print("SUCCESS:ARC-0050-probe2 mutations, FP budget, named hole")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
