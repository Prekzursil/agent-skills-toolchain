#!/usr/bin/env python3
"""Matched-pair harness: same case, seed, and budget on every arm.

Budget is applied by this harness. A workflow's requested_budget is ignored.
Failed arms are recorded and kept in the pair table. Variance floor is
measured from a control (same workflow twice) before any comparison is
reported. A |delta| at or below that floor is not a difference.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from fixtures import (
    BUDGET_LIMIT,
    BUDGET_UNIT,
    FUSION_CRASH,
    FUSION_HUNGRY,
    FUSION_UNION,
    NEAR_A,
    NEAR_B,
    SEED,
    SOURCE_RETRIEVE,
    SOURCE_TRANSFORM,
    UPSTREAM_CORPUS,
    UPSTREAM_FUSION,
    cases,
    comparison_workflows,
    control_workflows,
)


class PlantedCrash(RuntimeError):
    """Arm failure planted so the harness must retain a failed record."""


def canonical_dumps(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def input_fingerprint(case: dict, seed: int, budget_limit: float) -> str:
    """Hash of the matched input only — workflow id is excluded so arms match."""
    body = {
        "budget_limit": float(budget_limit),
        "case": {
            "id": case["id"],
            "family": case.get("family"),
            "oracle": case.get("oracle"),
            "payload": case.get("payload"),
            "required_capabilities": list(case.get("required_capabilities") or []),
        },
        "seed": int(seed),
    }
    return hashlib.sha256(canonical_dumps(body)).hexdigest()


def effective_budget(workflow: dict, harness_limit: float) -> float:
    """Harness-imposed limit. Workflow requested_budget is never consulted."""
    _ = workflow
    return float(harness_limit)


def classify_delta(delta: float, floor: float) -> dict:
    ad = abs(float(delta))
    fl = float(floor)
    if ad <= fl:
        return {
            "reported_as_difference": False,
            "classification": "not-a-difference",
            "reason": "abs(delta) <= variance_floor",
            "delta": float(delta),
            "abs_delta": ad,
            "floor": fl,
        }
    return {
        "reported_as_difference": True,
        "classification": "difference",
        "reason": "abs(delta) > variance_floor",
        "delta": float(delta),
        "abs_delta": ad,
        "floor": fl,
    }


def _oracle(collected: list[str], case: dict) -> tuple[str, float]:
    required = list(case.get("required_capabilities") or [])
    passed = all(item in collected for item in required)
    return ("pass" if passed else "fail", 1.0 if passed else 0.0)


def execute_arm(
    workflow: dict,
    case: dict,
    *,
    seed: int = SEED,
    budget_limit: float = BUDGET_LIMIT,
    seq: int = 0,
    phase: str = "comparison",
    clock: Callable[[], float] | None = None,
) -> dict:
    """Run one arm. Budget halt and crashes become records, never drops."""
    now = clock or time.perf_counter
    limit = effective_budget(workflow, budget_limit)
    fingerprint = input_fingerprint(case, seed, limit)
    remaining = limit
    collected: list[str] = []
    spent = 0.0
    executed = 0
    terminal = "completed"
    error = None
    t0 = now()
    try:
        for stage in workflow.get("stages") or []:
            cost = float(stage.get("cost") or 1.0)
            if cost > remaining:
                terminal = "budget-exhausted"
                break
            remaining -= cost
            spent += cost
            executed += 1
            if stage.get("action") == "crash":
                raise PlantedCrash(
                    f"planted crash in {workflow.get('id')}:{stage.get('id')}"
                )
            cap = stage.get("capability")
            if cap:
                collected.append(str(cap))
    except PlantedCrash as exc:
        terminal = "failed"
        error = str(exc)
    except Exception as exc:  # noqa: BLE001 — retain any arm failure
        terminal = "failed"
        error = f"{type(exc).__name__}:{exc}"
    wall_ms = round((now() - t0) * 1000.0, 6)
    if terminal == "failed":
        verdict, score = "not-run", None
    else:
        verdict, score = _oracle(collected, case)
    return {
        "run_id": f"{phase}:{workflow.get('id')}:{case['id']}:seq{seq}",
        "workflow_id": workflow.get("id"),
        "workflow_role": workflow.get("role"),
        "case_id": case["id"],
        "phase": phase,
        "seq": int(seq),
        "seed": int(seed),
        "budget_limit": float(limit),
        "budget_spent": float(spent),
        "budget_remaining": float(remaining),
        "requested_budget_ignored": workflow.get("requested_budget"),
        "input_hash": fingerprint,
        "wall_clock_ms": wall_ms,
        "terminal_state": terminal,
        "oracle_verdict": verdict,
        "oracle_score": score,
        "quality": None
        if terminal == "failed"
        else float(workflow.get("quality") or 0.0),
        "cost": float(spent),
        "stages_executed": executed,
        "stage_count": len(workflow.get("stages") or []),
        "capabilities": collected,
        "required_capabilities": list(case.get("required_capabilities") or []),
        "error": error,
        "dropped": False,
    }


def variance_floor(control_runs: list[dict], metric: str = "oracle_score") -> dict:
    groups: dict[tuple[str, str], list[float]] = {}
    for run in control_runs:
        val = run.get(metric)
        if val is None:
            continue
        key = (str(run.get("workflow_id")), str(run.get("case_id")))
        groups.setdefault(key, []).append(float(val))
    pairwise: list[dict] = []
    floor = 0.0
    for (wf, case_id), vals in sorted(groups.items()):
        if len(vals) < 2:
            continue
        delta = abs(vals[0] - vals[1])
        pairwise.append(
            {
                "workflow_id": wf,
                "case_id": case_id,
                "values": vals[:2],
                "abs_delta": delta,
            }
        )
        if delta > floor:
            floor = delta
    return {
        "metric": metric,
        "value": floor,
        "method": (
            "max abs pairwise delta of two control runs of the same workflow "
            "on the same case (identical seed, budget, input hash)"
        ),
        "control_pairs": pairwise,
        "control_run_count": len(control_runs),
    }


def compare_runs(
    left: dict, right: dict, floor: float | None, metric: str = "oracle_score"
) -> dict:
    if floor is None:
        raise RuntimeError("cannot compare before variance floor is measured")
    base = {
        "left_workflow": left.get("workflow_id"),
        "right_workflow": right.get("workflow_id"),
        "case_id": left.get("case_id"),
        "left_input_hash": left.get("input_hash"),
        "right_input_hash": right.get("input_hash"),
        "input_hashes_match": left.get("input_hash") == right.get("input_hash"),
        "budget_limits_match": left.get("budget_limit") == right.get("budget_limit"),
        "seeds_match": left.get("seed") == right.get("seed"),
        "dropped": False,
        "metric": metric,
        "floor": float(floor),
    }
    if left.get("terminal_state") == "failed" or right.get("terminal_state") == "failed":
        base.update(
            {
                "reported_as_difference": False,
                "classification": "failed-arm-retained",
                "reason": "failed arm kept in the pair table; no winner is declared",
                "left_terminal_state": left.get("terminal_state"),
                "right_terminal_state": right.get("terminal_state"),
            }
        )
        return base
    lv, rv = left.get(metric), right.get(metric)
    if lv is None or rv is None:
        base.update(
            {
                "reported_as_difference": False,
                "classification": "incomplete",
                "reason": "metric missing on at least one arm",
            }
        )
        return base
    classified = classify_delta(float(lv) - float(rv), floor)
    base.update(classified)
    base["left_value"] = float(lv)
    base["right_value"] = float(rv)
    return base


def run_experiment(
    *,
    seed: int = SEED,
    budget_limit: float = BUDGET_LIMIT,
    drop_failed: bool = False,
    planted_floor: float | None = None,
) -> dict:
    """Control phase first, then comparison phase. Floor gates reporting.

    drop_failed is a mutant switch: the live harness always keeps failed arms
    (drop_failed=False). Probe 2 turns it on to prove the detector fires.
    planted_floor, when set, is used only for the suppressor demonstration
    on quality; live oracle_score floor still comes from control doubles.
    """
    case_list = cases()
    controls = control_workflows()
    workflows = comparison_workflows()
    seq = 0
    control_runs: list[dict] = []

    for wf in controls:
        for case in case_list:
            for _repeat in range(2):
                seq += 1
                control_runs.append(
                    execute_arm(
                        wf,
                        case,
                        seed=seed,
                        budget_limit=budget_limit,
                        seq=seq,
                        phase="variance-floor",
                    )
                )

    max_control_seq = max(r["seq"] for r in control_runs)
    floor_oracle = variance_floor(control_runs, "oracle_score")
    floor_quality = variance_floor(control_runs, "quality")
    live_oracle_floor = float(floor_oracle["value"])

    comparison_runs: list[dict] = []
    for wf in workflows:
        for case in case_list:
            seq += 1
            run = execute_arm(
                wf,
                case,
                seed=seed,
                budget_limit=budget_limit,
                seq=seq,
                phase="comparison",
            )
            if drop_failed and run["terminal_state"] == "failed":
                continue
            comparison_runs.append(run)

    min_comparison_seq = min(
        (r["seq"] for r in comparison_runs), default=max_control_seq + 1
    )
    if min_comparison_seq <= max_control_seq:
        raise RuntimeError("comparison seq collided with control seq")

    by_wf_case = {(r["workflow_id"], r["case_id"]): r for r in comparison_runs}
    pair_specs = [
        (SOURCE_RETRIEVE, FUSION_UNION),
        (SOURCE_TRANSFORM, FUSION_UNION),
        (SOURCE_RETRIEVE, FUSION_CRASH),
        (FUSION_UNION, FUSION_HUNGRY),
        (NEAR_A, NEAR_B),
    ]
    comparisons: list[dict] = []
    pairs: list[dict] = []
    for left_id, right_id in pair_specs:
        for case in case_list:
            left = by_wf_case.get((left_id, case["id"]))
            right = by_wf_case.get((right_id, case["id"]))
            if left is None or right is None:
                pairs.append(
                    {
                        "left_workflow": left_id,
                        "right_workflow": right_id,
                        "case_id": case["id"],
                        "left_present": left is not None,
                        "right_present": right is not None,
                        "dropped_arm": True,
                    }
                )
                continue
            comparisons.append(
                compare_runs(left, right, live_oracle_floor, metric="oracle_score")
            )
            pairs.append(
                {
                    "left_workflow": left_id,
                    "right_workflow": right_id,
                    "case_id": case["id"],
                    "left_input_hash": left["input_hash"],
                    "right_input_hash": right["input_hash"],
                    "input_hashes_match": left["input_hash"] == right["input_hash"],
                    "left_budget_limit": left["budget_limit"],
                    "right_budget_limit": right["budget_limit"],
                    "left_seed": left["seed"],
                    "right_seed": right["seed"],
                    "left_terminal_state": left["terminal_state"],
                    "right_terminal_state": right["terminal_state"],
                    "left_present": True,
                    "right_present": True,
                    "dropped_arm": False,
                }
            )

    quality_floor_used = (
        float(planted_floor)
        if planted_floor is not None
        else float(floor_quality["value"])
    )
    quality_comparisons: list[dict] = []
    for case in case_list:
        left = by_wf_case.get((NEAR_A, case["id"]))
        right = by_wf_case.get((NEAR_B, case["id"]))
        if left and right:
            quality_comparisons.append(
                compare_runs(left, right, quality_floor_used, metric="quality")
            )

    failed_arms = [r for r in comparison_runs if r["terminal_state"] == "failed"]
    budget_exhausted_arms = [
        r for r in comparison_runs if r["terminal_state"] == "budget-exhausted"
    ]
    limits = {float(r["budget_limit"]) for r in comparison_runs}
    hashes_ok = all(
        p.get("input_hashes_match") for p in pairs if not p.get("dropped_arm")
    )
    any_pair_dropped = any(p.get("dropped_arm") for p in pairs)

    suppressor_controls = {
        "below_floor": classify_delta(0.01, 0.05),
        "above_floor": classify_delta(0.10, 0.05),
    }

    return {
        "seed": int(seed),
        "budget_limit": float(budget_limit),
        "budget_unit": BUDGET_UNIT,
        "drop_failed": bool(drop_failed),
        "cases": copy.deepcopy(case_list),
        "workflows": [
            {
                "id": w["id"],
                "role": w.get("role"),
                "title": w.get("title"),
                "lineage": list(w.get("lineage") or []),
                "stage_count": len(w.get("stages") or []),
                "requested_budget": w.get("requested_budget"),
                "quality": w.get("quality"),
            }
            for w in workflows
        ],
        "control_runs": control_runs,
        "comparison_runs": comparison_runs,
        "runs": control_runs + comparison_runs,
        "variance_floor": {
            "measured_before_comparisons": True,
            "max_control_seq": max_control_seq,
            "min_comparison_seq": min_comparison_seq,
            "oracle_score": floor_oracle,
            "quality": floor_quality,
            "live_oracle_floor": live_oracle_floor,
            "quality_floor_used": quality_floor_used,
        },
        "pairs": pairs,
        "comparisons": comparisons,
        "quality_comparisons": quality_comparisons,
        "suppressor_controls": suppressor_controls,
        "failed_arms": [
            {
                "workflow_id": r["workflow_id"],
                "case_id": r["case_id"],
                "terminal_state": r["terminal_state"],
                "oracle_verdict": r["oracle_verdict"],
                "dropped": r["dropped"],
                "error": r["error"],
            }
            for r in failed_arms
        ],
        "budget_exhausted_arms": [
            {
                "workflow_id": r["workflow_id"],
                "case_id": r["case_id"],
                "budget_limit": r["budget_limit"],
                "budget_spent": r["budget_spent"],
                "stages_executed": r["stages_executed"],
                "stage_count": r["stage_count"],
                "terminal_state": r["terminal_state"],
            }
            for r in budget_exhausted_arms
        ],
        "budget_parity": {
            "equal": len(limits) == 1,
            "budget_limit": float(budget_limit) if len(limits) == 1 else sorted(limits),
            "unit": BUDGET_UNIT,
            "runs_compared": len(comparison_runs),
            "distinct_limits": sorted(limits),
            "enforced_by": "harness",
        },
        "input_hash_parity": {
            "all_matched_pairs_agree": hashes_ok,
            "pair_count": len(pairs),
        },
        "failed_arm_accounting": {
            "failed_count": len(failed_arms),
            "any_pair_dropped": any_pair_dropped,
            "drop_failed_mutant": bool(drop_failed),
        },
    }


def inventory(repo: Path | str) -> dict:
    root = Path(repo)
    rels = [UPSTREAM_CORPUS, *UPSTREAM_FUSION]
    present, absent = [], []
    for rel in rels:
        path = root / rel
        if path.is_file() and path.stat().st_size > 0:
            present.append(rel)
        else:
            absent.append(rel)
    return {
        "checked": rels,
        "present": present,
        "absent": absent,
        "corpus_present": UPSTREAM_CORPUS in present,
        "fusion_operator_artifacts_present": any(
            "FUSION" in p.upper() for p in present
        ),
        "subject": (
            "WFA-0112 corpus and fusion-operator artifacts are absent on this "
            "Linux worktree. WFA-0113 runs a fixture corpus and fixture source/"
            "fusion workflows so the matched-pair contract is executable here. "
            "The harness would consume those artifacts unchanged when present."
        ),
    }
