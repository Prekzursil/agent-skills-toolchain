#!/usr/bin/env python3
"""Probe 1: intersection is computed mechanically; union is not the pairing set.

Signal 1: set.intersection of per-workflow runnable ids.
Signal 2 (independent): per-case all(can_run) scan.
A union that includes format/secret/exotic cases must not equal the intersection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from bench.matched_pairing import (  # noqa: E402
    can_run,
    load_scenario,
    pair_comparison,
    runnable_ids,
)

SCENARIO = HERE / "fixtures" / "scenario.json"
ART = REPO / "command-center/receipts/TST-0296.json"
LINT_N = 12


def fail(msg: str) -> int:
    print(f"FAILED:TST-0296-probe1 {msg}")
    return 1


def main() -> int:
    scenario = load_scenario(SCENARIO)
    cases = scenario["cases"]
    workflows = scenario["workflows"]
    cmpn = next(c for c in scenario["comparisons"] if c["id"] == "cmp-h2h-sufficient")
    result = pair_comparison(
        cases=cases,
        workflows=workflows,
        fusion_id=cmpn["fusion"],
        source_ids=list(cmpn["sources"]),
        min_intersection=int(cmpn["min_intersection"]),
        comparison_id=cmpn["id"],
    )

    alpha = runnable_ids(workflows["src.alpha"], cases)
    beta = runnable_ids(workflows["src.beta"], cases)
    inter_sets = alpha & beta
    inter_scan = {
        str(c["id"])
        for c in cases
        if can_run(workflows["src.alpha"], c) and can_run(workflows["src.beta"], c)
    }
    if inter_sets != inter_scan:
        return fail("signals disagree")
    if set(result["intersection_case_ids"]) != inter_sets:
        return fail("engine intersection != mechanical sets")
    if result["intersection_size"] != LINT_N:
        return fail(f"intersection_size={result['intersection_size']} want={LINT_N}")
    lint_ids = {str(c["id"]) for c in cases if c["required_capabilities"] == ["lint"]}
    if set(result["intersection_case_ids"]) != lint_ids:
        return fail("intersection is not the lint lane")

    source_union = alpha | beta
    if source_union == inter_sets:
        return fail("union equals intersection; pairing is unfalsifiable")
    extra = sorted(source_union - inter_sets)
    if not extra:
        return fail("no asymmetric source cases to exclude")
    if result["comparison_status"] != "COMPARABLE":
        return fail(f"status={result['comparison_status']}")
    excluded_ids = {row["case_id"] for row in result["excluded"]}
    corpus = {str(c["id"]) for c in cases}
    if excluded_ids | set(result["intersection_case_ids"]) != corpus:
        return fail("exclusion list does not partition the corpus")
    if result["reported_win"]:
        return fail("pairing declared a win from coverage arithmetic")
    if result["excluded_count"] < 1:
        return fail("empty exclusion list on a reported comparison")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        published = None
        for row in doc.get("comparisons") or []:
            if row.get("comparison_id") == "cmp-h2h-sufficient":
                published = row
                break
        if published is None:
            return fail("receipt missing cmp-h2h-sufficient")
        if published.get("intersection_size") != result["intersection_size"]:
            return fail("receipt intersection_size mismatch")
        pub_ex = [e["case_id"] for e in published.get("excluded") or []]
        if sorted(pub_ex) != sorted(excluded_ids):
            return fail("receipt exclusion ids mismatch")
        if "SUCCESS:TST-0296" not in json.dumps(doc):
            return fail("receipt sentinel absent")

    summary = {
        "probe": "probe1-intersection",
        "unit_id": "TST-0296",
        "intersection_size": result["intersection_size"],
        "union_size": len(source_union),
        "excluded_count": result["excluded_count"],
        "signals_agree": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"intersection={result['intersection_size']} "
        f"union={len(source_union)} excluded={result['excluded_count']} "
        f"extra_in_union={extra}"
    )
    print("SUCCESS:TST-0296-probe1 mechanical intersection vs union")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
