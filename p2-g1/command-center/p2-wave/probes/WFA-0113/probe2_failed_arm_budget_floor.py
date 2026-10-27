#!/usr/bin/env python3
"""Probe 2: failed arm retained, budget enforced, below-floor not reported.

Both-states:
  * drop_failed=False keeps the crash arm; drop_failed=True drops it (detector fires).
  * classify_delta(0.01, 0.05) is not a difference; classify_delta(0.10, 0.05) is.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    BUDGET_LIMIT,
    FUSION_CRASH,
    FUSION_HUNGRY,
    SEED,
    fusion_hungry,
)
from harness import classify_delta, effective_budget, run_experiment  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json"
SENTINEL = "SUCCESS:WFA-0113"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0113-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    kept = run_experiment(seed=SEED, budget_limit=BUDGET_LIMIT, planted_floor=0.05)
    dropped = run_experiment(
        seed=SEED, budget_limit=BUDGET_LIMIT, drop_failed=True, planted_floor=0.05
    )

    crash_kept = [
        r
        for r in kept["comparison_runs"]
        if r["workflow_id"] == FUSION_CRASH and r["terminal_state"] == "failed"
    ]
    crash_in_dropped = [
        r for r in dropped["comparison_runs"] if r["workflow_id"] == FUSION_CRASH
    ]
    if not crash_kept:
        return fail("live harness produced no failed crash arm")
    if any(r.get("dropped") for r in crash_kept):
        return fail("crash arm marked dropped")
    crash_pairs = [
        p
        for p in kept["pairs"]
        if FUSION_CRASH in (p.get("left_workflow"), p.get("right_workflow"))
    ]
    if not crash_pairs or any(p.get("dropped_arm") for p in crash_pairs):
        return fail("crash arm missing from pair table")
    if crash_in_dropped:
        return fail("drop_failed mutant still retained crash runs")
    dropped_crash_pairs = [
        p
        for p in dropped["pairs"]
        if FUSION_CRASH in (p.get("left_workflow"), p.get("right_workflow"))
        and p.get("dropped_arm")
    ]
    if not dropped_crash_pairs:
        return fail("drop_failed mutant did not mark crash pairs dropped")

    hungry = [r for r in kept["comparison_runs"] if r["workflow_id"] == FUSION_HUNGRY]
    if not hungry:
        return fail("no hungry fusion runs")
    for run in hungry:
        if run["terminal_state"] != "budget-exhausted":
            return fail(f"hungry terminal {run['terminal_state']}")
        if float(run["budget_spent"]) > float(run["budget_limit"]):
            return fail("hungry spent past limit")
        if int(run["stages_executed"]) >= int(run["stage_count"]):
            return fail("hungry executed every stage")
        ignored = run.get("requested_budget_ignored")
        if ignored is None or float(ignored) <= float(run["budget_limit"]):
            return fail("requested_budget was not a larger ignored value")
        if float(run["budget_limit"]) != float(BUDGET_LIMIT):
            return fail("hungry used workflow-requested budget")

    wf = fusion_hungry()
    if effective_budget(wf, BUDGET_LIMIT) != float(BUDGET_LIMIT):
        return fail("effective_budget consulted workflow request")
    if float(wf["requested_budget"]) == float(BUDGET_LIMIT):
        return fail("fixture requested_budget is not distinct from harness limit")

    below = classify_delta(0.01, 0.05)
    above = classify_delta(0.10, 0.05)
    equal = classify_delta(0.0, 0.0)
    if below["reported_as_difference"] or below["classification"] != "not-a-difference":
        return fail("0.01 vs floor 0.05 was reported as a difference")
    if not above["reported_as_difference"] or above["classification"] != "difference":
        return fail("0.10 vs floor 0.05 was not reported as a difference")
    if equal["reported_as_difference"]:
        return fail("zero delta reported as difference")
    if any(row.get("reported_as_difference") for row in kept["quality_comparisons"]):
        return fail("near-twin quality delta reported under planted floor 0.05")

    art_failed = doc.get("failed_arms") or []
    if not art_failed:
        return fail("artifact omitted failed_arms")
    if any(a.get("dropped") for a in art_failed):
        return fail("artifact marked failed arms dropped")
    art_hungry = doc.get("budget_exhausted_arms") or []
    if not art_hungry:
        return fail("artifact omitted budget_exhausted_arms")
    art_below = (doc.get("suppressor_controls") or {}).get("below_floor") or {}
    art_above = (doc.get("suppressor_controls") or {}).get("above_floor") or {}
    if art_below.get("reported_as_difference"):
        return fail("artifact reported below-floor as difference")
    if not art_above.get("reported_as_difference"):
        return fail("artifact omitted above-floor difference")

    summary = {
        "probe": "probe2-failed-arm-budget-floor",
        "unit_id": "WFA-0113",
        "crash_kept": len(crash_kept),
        "crash_dropped_by_mutant": len(dropped_crash_pairs),
        "hungry_halted": len(hungry),
        "below_floor_reported": below["reported_as_difference"],
        "above_floor_reported": above["reported_as_difference"],
        "silent_on_good_state": True,
        "fired_on_bad_state": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "crash_kept={0} mutant_dropped={1} hungry={2} below={3} above={4}".format(
            len(crash_kept),
            len(dropped_crash_pairs),
            len(hungry),
            below["reported_as_difference"],
            above["reported_as_difference"],
        )
    )
    print(
        "SUCCESS:WFA-0113-probe2 failed-arm retained, budget halted, below-floor suppressed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
