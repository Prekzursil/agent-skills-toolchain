#!/usr/bin/env python3
"""Probe 2: near-miss disclosure + mutant that omits near-misses must go red.

Failure class: explanation-omits-near-miss. Reconstructing the selected set
can still succeed after the omission; the disclosure check must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "router"))

import explain as E  # noqa: E402
import scenario as S  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0395.json"


def check_case(case: dict, expl: dict) -> str | None:
    required = set(case["gold_near_misses"])
    if not required:
        return f"{case['query_id']}: gold near-misses empty (corpus defect)"
    ok, why = E.discloses_near_misses(expl, required)
    if not ok:
        return f"{case['query_id']}: live explanation {why}"
    rec = E.reconstruct_selected(expl)
    if rec != list(case["gold_selected"]):
        return f"{case['query_id']}: live reconstruct {rec} != gold {case['gold_selected']}"
    for row in expl["near_misses"]:
        if not row.get("cutoff_reason") or not row.get("capability_id"):
            return f"{case['query_id']}: near-miss missing cutoff_reason"
    return None


def mutant_empty_near_misses(expl: dict, required: set[str]) -> bool:
    mutant = copy.deepcopy(expl)
    mutant["near_misses"] = []
    ok, _ = E.discloses_near_misses(mutant, required)
    rec = E.reconstruct_selected(mutant)
    selected_ok = rec == E.reconstruct_selected(expl)
    # Disclosure MUST fail. Selected reconstruction MAY still pass.
    return (not ok) and selected_ok


def mutant_strip_near_miss_rows(expl: dict, required: set[str], gold_selected: list[str]) -> bool:
    mutant = copy.deepcopy(expl)
    mutant["candidates"] = [
        c for c in mutant["candidates"] if c["capability_id"] not in required
    ]
    mutant["near_misses"] = [
        n for n in mutant["near_misses"] if n["capability_id"] not in required
    ]
    ok, _ = E.discloses_near_misses(mutant, required)
    rec = E.reconstruct_selected(mutant)
    return (not ok) and rec == gold_selected


def main() -> int:
    live_n = 0
    for case in S.cases():
        expl = E.explain_one(S.case_to_trace(case), S.load_index())
        err = check_case(case, expl)
        if err:
            print("FAILED:IMP-0395-probe2", err)
            return 1
        required = set(case["gold_near_misses"])
        if not mutant_empty_near_misses(expl, required):
            print("FAILED:IMP-0395-probe2 empty-near-miss mutant was accepted", case["query_id"])
            return 1
        if not mutant_strip_near_miss_rows(expl, required, list(case["gold_selected"])):
            print(
                "FAILED:IMP-0395-probe2 strip-candidate mutant was accepted",
                case["query_id"],
            )
            return 1
        print(
            f"{case['query_id']} near_misses={[n['capability_id'] for n in expl['near_misses']]} "
            f"mutants_rejected=True"
        )
        live_n += 1
    if live_n < 3:
        print("FAILED:IMP-0395-probe2 fewer than 3 cases")
        return 1

    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        by_qid = {e["query_id"]: e for e in (doc.get("explanations") or [])}
        for case in S.cases():
            expl = by_qid.get(case["query_id"])
            if not expl:
                print("FAILED:IMP-0395-probe2 receipt missing", case["query_id"])
                return 1
            err = check_case(case, expl)
            if err:
                print("FAILED:IMP-0395-probe2 receipt", err)
                return 1
            required = set(case["gold_near_misses"])
            if not mutant_empty_near_misses(expl, required):
                print("FAILED:IMP-0395-probe2 receipt mutant accepted", case["query_id"])
                return 1
        if "SENTINEL:IMP-0395:EXPLANATION-RECONSTRUCTIBLE" not in RECEIPT.read_text(encoding="utf-8"):
            print("FAILED:IMP-0395-probe2 sentinel absent")
            return 1

    print("SUCCESS:IMP-0395-probe2 near-miss disclosure and omit-mutant goes red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
