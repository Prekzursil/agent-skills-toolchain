#!/usr/bin/env python3
"""Probe 1: equal billed budget, negative-control variance, live recount."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

UNIT = "RES-0190"
OUT = REPO / (
    "command-center/research/deep-research-design/"
    "RES-0190-breadth-versus-depth-budget-allocation.json"
)
SENTINEL = "SUCCESS:RES-0190"
BUDGET_ARM = E.BUDGET_PER_QUESTION * 3


def fail(msg: str) -> int:
    print(f"FAILED:RES-0190-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in OUT.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    live = E.run_experiment()
    art_totals = doc.get("totals_mechanism") or {}
    live_totals = live["totals_mechanism"]
    print(f"live_totals={live_totals}")
    print(f"artifact_totals={art_totals}")
    if art_totals != live_totals:
        return fail(f"totals drifted live={live_totals} artifact={art_totals}")

    for split, arm in live["arms"].items():
        billed = int(arm["billed_total"])
        print(f"arm {split} billed={billed} cap={BUDGET_ARM} ok={arm['budget_ok']}")
        if billed != BUDGET_ARM or not arm["budget_ok"]:
            return fail(f"{split} billed {billed} != {BUDGET_ARM}")
        for q in arm["questions"]:
            if int(q["billed_total"]) != E.BUDGET_PER_QUESTION:
                return fail(
                    f"{split} {q['question_id']} billed {q['billed_total']}"
                )
            if int(q["scan_spent"]) + int(q["verify_spent"]) + int(q["waste"]) != E.BUDGET_PER_QUESTION:
                return fail(f"{split} {q['question_id']} spend+waste identity")

    billed_set = {arm["billed_total"] for arm in live["arms"].values()}
    if billed_set != {BUDGET_ARM}:
        return fail(f"unequal arm bills {billed_set}")

    nc = live["negative_control"]
    print(
        f"negative_control a={nc['run_a_distinct']} b={nc['run_b_distinct']} "
        f"variance={nc['variance']}"
    )
    if nc["variance"] != abs(nc["run_a_distinct"] - nc["run_b_distinct"]):
        return fail("variance arithmetic")
    art_nc = doc.get("negative_control") or {}
    if int(art_nc.get("variance", -1)) != int(nc["variance"]):
        return fail("artifact variance drifted")

    policy = live["policy"]
    art_policy = doc.get("policy") or {}
    print(f"policy={policy['headline']} winner={policy.get('winner')}")
    if policy.get("winner") != art_policy.get("winner"):
        return fail("winner drifted")
    if policy.get("headline") != art_policy.get("headline"):
        return fail("headline drifted")
    gap = int(policy["gap"])
    var = int(policy["variance"])
    if gap <= var and policy.get("winner") is not None:
        return fail("winner claimed despite gap <= variance")
    if gap > var and not policy.get("winner"):
        return fail("gap exceeds variance but no winner")

    mutant = dict(live_totals)
    mutant["80/20"] = mutant["80/20"] + 1
    if mutant == live_totals:
        return fail("mutant did not change totals")
    # Detector both-states: a +1 mutant must not match the artifact.
    if mutant == art_totals:
        return fail("artifact accepted mutated totals")

    print("budget_equal=True negative_control_ok=True recount_match=True")
    print("SUCCESS:RES-0190-probe1 equal budget and variance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
