"""Run the labelled TST-0318 matrix: budgeted vs flood vs starve."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metrics import (
    all_over_budget,
    all_under_budget,
    composite_cell_pass,
    configuration_pair,
    gold_offered,
    mean_cost,
    micro_offer_recall,
    per_capability_offer_table,
)
from router import (
    FALLBACK_ID,
    TOKEN_BUDGET,
    TOP_K,
    count_tokens,
    inject,
    payload_for,
)

HERE = Path(__file__).resolve().parent
POLICIES = ("budgeted", "flood", "starve")
WORKFLOWS = {
    "budgeted": {
        "id": "wf.budgeted-topk",
        "role": "fusion",
        "stage_count": 3,
        "budget_limit": TOKEN_BUDGET,
    },
    "flood": {
        "id": "wf.flood-catalogue",
        "role": "source",
        "stage_count": 1,
        "budget_limit": TOKEN_BUDGET,
    },
    "starve": {
        "id": "wf.starve-inject-nothing",
        "role": "source",
        "stage_count": 1,
        "budget_limit": TOKEN_BUDGET,
    },
}
KNOWN_MISS_CASE = "case.fc11330-installed-skill"
KNOWN_MISS_SKILL = "skill.deploy-parity-live-tree"


def load_json(name: str) -> dict[str, Any]:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def load_repertoire() -> dict[str, Any]:
    return load_json("repertoire.json")


def load_labelled() -> dict[str, Any]:
    return load_json("labelled_set.json")


def capabilities() -> list[dict[str, Any]]:
    return list(load_repertoire()["capabilities"])


def cases() -> list[dict[str, Any]]:
    return list(load_labelled()["cases"])


def run_policy(policy: str, caps: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    pool = capabilities() if caps is None else caps
    out = []
    for case in cases():
        sel = inject(str(case["prompt"]), pool, policy=policy)
        passed = composite_cell_pass(case, sel)
        out.append(
            {
                "case_id": case["id"],
                "expected": case["expected"],
                "kind": case["kind"],
                "gold_offered": gold_offered(case, sel),
                "passed": passed,
                **sel,
            }
        )
    return out


def evaluate() -> dict[str, Any]:
    caps = capabilities()
    labelled = cases()
    by_policy: dict[str, list[dict[str, Any]]] = {
        p: run_policy(p, caps) for p in POLICIES
    }
    tables = {
        p: per_capability_offer_table(labelled, by_policy[p]) for p in POLICIES
    }
    pairs = {
        p: configuration_pair(p, labelled, by_policy[p]) for p in POLICIES
    }

    cells = []
    for policy, wf in WORKFLOWS.items():
        for case, pred in zip(labelled, by_policy[policy]):
            cells.append(
                {
                    "workflow_id": wf["id"],
                    "case_id": case["id"],
                    "score": 1.0 if pred["passed"] else 0.0,
                    "budget_limit": wf["budget_limit"],
                    "budget_spent": int(pred["injected_token_cost"]),
                    "stage_count": wf["stage_count"],
                    "passed": bool(pred["passed"]),
                    "offered_ids": list(pred["offered_ids"]),
                    "expected": case["expected"],
                    "gold_offered": bool(pred["gold_offered"]),
                }
            )

    workflows = []
    for policy, wf in WORKFLOWS.items():
        preds = by_policy[policy]
        pair = pairs[policy]
        workflows.append(
            {
                "id": wf["id"],
                "role": wf["role"],
                "stage_count": wf["stage_count"],
                "budget_limit": wf["budget_limit"],
                "budget_spent_mean": pair["injected_token_cost_mean"],
                "pass_rate": (sum(1 for p in preds if p["passed"]) / len(preds))
                if preds
                else 0.0,
                "recall": pair["recall"],
                "injected_token_cost_mean": pair["injected_token_cost_mean"],
                "injected_token_cost_max": pair["injected_token_cost_max"],
                "budget_ok": pair["budget_ok"],
            }
        )

    fusion_preds = {p["case_id"]: p for p in by_policy["budgeted"]}
    regressions = []
    for src_policy in ("flood", "starve"):
        for case, pred in zip(labelled, by_policy[src_policy]):
            f = fusion_preds[case["id"]]
            regressions.append(
                {
                    "case_id": case["id"],
                    "source_id": WORKFLOWS[src_policy]["id"],
                    "fusion_score": 1.0 if f["passed"] else 0.0,
                    "source_score": 1.0 if pred["passed"] else 0.0,
                }
            )
    fusion_worse = [r for r in regressions if r["fusion_score"] < r["source_score"]]

    fusion_pass = next(w["pass_rate"] for w in workflows if w["role"] == "fusion")
    source_pass = [w["pass_rate"] for w in workflows if w["role"] == "source"]
    outperforms = fusion_pass > max(source_pass) + 1e-9

    miss_case = next(c for c in labelled if c["id"] == KNOWN_MISS_CASE)
    miss_budgeted = next(
        p for p in by_policy["budgeted"] if p["case_id"] == KNOWN_MISS_CASE
    )
    miss_flood = next(p for p in by_policy["flood"] if p["case_id"] == KNOWN_MISS_CASE)
    miss_installed = any(c["id"] == KNOWN_MISS_SKILL for c in caps)

    flood_payload = payload_for(caps)
    flood_measured = count_tokens(flood_payload)
    flood_estimate = sum(int(c.get("token_cost") or 0) for c in caps)

    tests = {
        "test_recall_on_labelled_gold_set": (
            all(pairs[p]["pair_complete"] for p in POLICIES)
            and pairs["budgeted"]["recall"] > 0.5
            and pairs["flood"]["recall"] == 1.0
        ),
        "test_injected_token_cost_measured_per_task": (
            all(int(p["injected_token_cost"]) >= 0 for preds in by_policy.values() for p in preds)
            and flood_measured == pairs["flood"]["injected_token_cost_max"]
            and flood_measured != flood_estimate
            and pairs["starve"]["injected_token_cost_mean"] == 0.0
        ),
        "test_flooding_control_perfect_recall_fails_budget": (
            pairs["flood"]["recall"] == 1.0
            and all_over_budget(by_policy["flood"])
            and flood_measured > TOKEN_BUDGET
        ),
        "test_known_miss_11330_in_suite": (
            miss_installed
            and str(miss_case["expected"]) == KNOWN_MISS_SKILL
            and miss_flood["gold_offered"] is True
            and miss_budgeted["gold_offered"] is False
            and KNOWN_MISS_SKILL not in miss_budgeted["offered_ids"]
        ),
        "test_budgeted_stays_under_budget": all_under_budget(by_policy["budgeted"]),
        "test_starve_zero_cost_zero_recall": (
            pairs["starve"]["recall"] == 0.0
            and pairs["starve"]["injected_token_cost_mean"] == 0.0
        ),
        "test_pair_on_every_configuration": all(
            "recall" in pairs[p] and "injected_token_cost_mean" in pairs[p] for p in POLICIES
        ),
    }

    mutant_caps = [c for c in caps if c["id"] != KNOWN_MISS_SKILL]
    mutant_flood = inject(str(miss_case["prompt"]), mutant_caps, policy="flood")
    tests["test_mutation_uninstall_known_miss_drops_flood_offer"] = (
        KNOWN_MISS_SKILL not in mutant_flood["offered_ids"]
    )

    return {
        "policies": by_policy,
        "tables": tables,
        "pairs": pairs,
        "cells": cells,
        "workflows": workflows,
        "regressions": regressions,
        "fusion_worse": fusion_worse,
        "outperforms": outperforms,
        "tests": tests,
        "labelled": labelled,
        "repertoire": caps,
        "flood_measured": flood_measured,
        "flood_estimate": flood_estimate,
        "token_budget": TOKEN_BUDGET,
        "top_k": TOP_K,
        "known_miss": {
            "case_id": KNOWN_MISS_CASE,
            "capability_id": KNOWN_MISS_SKILL,
            "installed": miss_installed,
            "budgeted_offered": miss_budgeted["gold_offered"],
            "flood_offered": miss_flood["gold_offered"],
        },
        "fallback_id": FALLBACK_ID,
        "mean_cost": {p: mean_cost(by_policy[p]) for p in POLICIES},
        "micro_recall": {p: micro_offer_recall(labelled, by_policy[p]) for p in POLICIES},
    }
