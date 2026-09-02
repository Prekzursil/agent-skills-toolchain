#!/usr/bin/env python3
"""Local matched-pair substrate: deterministic workflows, oracles, raw run records.

WFA-0113/0115/0116 catalog artifacts are absent on this worktree. This module
is the unit-local stand-in that produces raw run records (input hashes, seeds,
budgets, oracle verdicts, costs) so WFA-0117 can review from runs, not from a
fusion-lane summary.
"""
from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from typing import Any, Callable

SEED = 7
BUDGET = 100

CASES: list[dict[str, Any]] = [
    {"id": "case.alpha", "input": {"n": 4}},
    {"id": "case.beta", "input": {"words": ["a", "bb", "ccc"]}},
    {"id": "case.gamma", "input": {"items": [3, 1, 2]}},
    {"id": "case.delta", "input": {"text": "abba"}},
]

# Held-out perturbation of case.alpha: genuine solvers follow n, gaming tables do not.
PERTURBED_ALPHA = {"id": "case.alpha", "input": {"n": 5}}

WORKFLOW_IDS = (
    "source_alpha",
    "source_beta",
    "fused_complement",
    "fused_worse",
    "fused_gaming",
)

SOURCE_IDS = ("source_alpha", "source_beta")
FUSED_IDS = ("fused_complement", "fused_worse", "fused_gaming")

# Declared cost units. Gaming is suspiciously cheap; complement pays for coverage.
COSTS = {
    "source_alpha": 20,
    "source_beta": 20,
    "fused_complement": 35,
    "fused_worse": 10,
    "fused_gaming": 1,
}

REPRODUCE_TRIPLE = (
    ("fused_complement", "case.delta"),
    ("fused_worse", "case.alpha"),
    ("fused_gaming", "case.alpha"),
)


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def input_hash(case_id: str, inp: dict, seed: int, budget: int) -> str:
    blob = canonical(
        {"case_id": case_id, "input": inp, "seed": seed, "budget": budget}
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def oracle(case: dict, artifact: dict) -> bool:
    cid = case["id"]
    inp = case["input"]
    if not isinstance(artifact, dict):
        return False
    if cid == "case.alpha":
        n = int(inp["n"])
        return artifact.get("sum") == n * (n + 1) // 2
    if cid == "case.beta":
        words = list(inp["words"])
        return artifact.get("lengths") == [len(w) for w in words]
    if cid == "case.gamma":
        return artifact.get("sorted") == sorted(inp["items"])
    if cid == "case.delta":
        text = str(inp["text"])
        return artifact.get("palindrome") is (text == text[::-1])
    return False


def _unsupported() -> dict:
    return {"unsupported": True}


def source_alpha(case: dict) -> dict:
    cid, inp = case["id"], case["input"]
    if cid == "case.alpha":
        n = int(inp["n"])
        return {"sum": n * (n + 1) // 2}
    if cid == "case.gamma":
        return {"sorted": sorted(inp["items"])}
    return _unsupported()


def source_beta(case: dict) -> dict:
    cid, inp = case["id"], case["input"]
    if cid == "case.beta":
        return {"lengths": [len(w) for w in inp["words"]]}
    if cid == "case.gamma":
        return {"sorted": sorted(inp["items"])}
    return _unsupported()


def fused_complement(case: dict) -> dict:
    cid, inp = case["id"], case["input"]
    if cid == "case.alpha":
        n = int(inp["n"])
        return {"sum": n * (n + 1) // 2}
    if cid == "case.beta":
        return {"lengths": [len(w) for w in inp["words"]]}
    if cid == "case.gamma":
        return {"sorted": sorted(inp["items"])}
    if cid == "case.delta":
        text = str(inp["text"])
        return {"palindrome": text == text[::-1]}
    return _unsupported()


def fused_worse(case: dict) -> dict:
    if case["id"] == "case.gamma":
        return {"sorted": sorted(case["input"]["items"])}
    return _unsupported()


def fused_gaming(case: dict) -> dict:
    # Oracle-shaped constants for the *original* corpus only. A genuine solver
    # follows the input; this table does not.
    table = {
        "case.alpha": {"sum": 10},
        "case.beta": {"lengths": [1, 2, 3]},
        "case.gamma": {"sorted": [1, 2, 3]},
        "case.delta": {"palindrome": True},
    }
    return deepcopy(table.get(case["id"], _unsupported()))


RUNNERS: dict[str, Callable[[dict], dict]] = {
    "source_alpha": source_alpha,
    "source_beta": source_beta,
    "fused_complement": fused_complement,
    "fused_worse": fused_worse,
    "fused_gaming": fused_gaming,
}


def run_one(
    workflow_id: str,
    case: dict,
    seed: int = SEED,
    budget: int = BUDGET,
) -> dict[str, Any]:
    if workflow_id not in RUNNERS:
        raise KeyError(workflow_id)
    if budget != BUDGET:
        raise ValueError("budget parity is harness-enforced")
    t0 = time.perf_counter_ns()
    artifact = RUNNERS[workflow_id](case)
    wall_ns = time.perf_counter_ns() - t0
    passed = oracle(case, artifact)
    terminal = "ok" if passed else (
        "unsupported" if artifact.get("unsupported") else "oracle-fail"
    )
    ih = input_hash(case["id"], case["input"], seed, budget)
    return {
        "run_id": f"{workflow_id}::{case['id']}::seed={seed}",
        "workflow_id": workflow_id,
        "case_id": case["id"],
        "seed": seed,
        "budget": budget,
        "input": deepcopy(case["input"]),
        "input_hash": ih,
        "artifact": artifact,
        "oracle_pass": passed,
        "cost_units": COSTS[workflow_id],
        "terminal_state": terminal,
        "wall_ns": wall_ns,
    }


def collect_raw_records(seed: int = SEED, budget: int = BUDGET) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for wf in WORKFLOW_IDS:
        for case in CASES:
            rows.append(run_one(wf, case, seed=seed, budget=budget))
    # Variance-floor control: same workflow twice on the same case.
    rows.append(run_one("source_alpha", CASES[2], seed=seed, budget=budget))
    rows[-1]["run_id"] = rows[-1]["run_id"] + "::repeat"
    rows[-1]["control"] = "same-workflow-twice"
    return rows


def records_by_workflow(records: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in records:
        if row.get("control") == "same-workflow-twice":
            continue
        out.setdefault(row["workflow_id"], []).append(row)
    return out


def variance_floor(records: list[dict]) -> dict[str, Any]:
    """Control arm: same workflow twice. A difference smaller than this floor
    is not a difference. Deterministic workflows yield floor 0 — that is a
    measurement, not an assumption.
    """
    primary = [
        r
        for r in records
        if r["workflow_id"] == "source_alpha"
        and r["case_id"] == "case.gamma"
        and r.get("control") != "same-workflow-twice"
    ]
    repeats = [
        r
        for r in records
        if r.get("control") == "same-workflow-twice"
        and r["case_id"] == "case.gamma"
    ]
    if not primary or not repeats:
        return {"measured": False, "floor": None, "reason": "control arm missing"}
    a, b = primary[0], repeats[0]
    same_hash = a["input_hash"] == b["input_hash"]
    same_oracle = a["oracle_pass"] == b["oracle_pass"]
    same_cost = a["cost_units"] == b["cost_units"]
    floor = 0.0 if (same_hash and same_oracle and same_cost) else 1.0
    return {
        "measured": True,
        "floor": floor,
        "same_input_hash": same_hash,
        "same_oracle": same_oracle,
        "same_cost": same_cost,
        "pair": [a["run_id"], b["run_id"]],
        "method": (
            "same workflow (source_alpha) twice on case.gamma with identical "
            "seed and budget; floor is 0 iff oracle and cost match"
        ),
    }


def budget_parity(records: list[dict]) -> bool:
    budgets = {r["budget"] for r in records}
    return budgets == {BUDGET}


def case_by_id(case_id: str) -> dict[str, Any]:
    for case in CASES:
        if case["id"] == case_id:
            return case
    raise KeyError(case_id)


def failed_arms_retained(records: list[dict]) -> bool:
    """An arm that fails to produce a passing artifact is still in the comparison."""
    by = records_by_workflow(records)
    for wf in WORKFLOW_IDS:
        rows = by.get(wf) or []
        if len(rows) != len(CASES):
            return False
        if not any(not r["oracle_pass"] for r in rows) and wf != "fused_complement" and wf != "fused_gaming":
            # source_alpha/beta/worse must have failures; complement/gaming pass all original cases
            pass
    return True
