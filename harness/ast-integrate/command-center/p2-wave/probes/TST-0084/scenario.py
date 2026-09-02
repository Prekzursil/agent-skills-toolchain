"""Run the labelled TST-0084 matrix: full repertoire vs two degenerate sources."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metrics import (
    macro_recall,
    micro_recall,
    overclaim_hidden_zero,
    per_capability_table,
    zero_recall_capabilities,
)
from router import FALLBACK_ID, route

HERE = Path(__file__).resolve().parent
POLICIES = ("full", "usage-pruned", "popularity-greedy")
WORKFLOWS = {
    "full": {
        "id": "wf.full-repertoire",
        "role": "fusion",
        "stage_count": 3,
        "budget_limit": 80,
    },
    "usage-pruned": {
        "id": "wf.usage-pruned",
        "role": "source",
        "stage_count": 1,
        "budget_limit": 80,
    },
    "popularity-greedy": {
        "id": "wf.popularity-greedy",
        "role": "source",
        "stage_count": 1,
        "budget_limit": 80,
    },
}
RARE_IDS = frozenset({"skill.nul-device-census", "skill.windows-long-path"})


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
        sel = route(str(case["prompt"]), pool, policy=policy)
        passed = str(sel["capability_id"]) == str(case["expected"])
        if str(case["expected"]) == FALLBACK_ID:
            passed = passed and (sel["confident"] is False)
        row = {
            "case_id": case["id"],
            "expected": case["expected"],
            "kind": case["kind"],
            "passed": passed,
            **sel,
        }
        out.append(row)
    return out


def evaluate() -> dict[str, Any]:
    caps = capabilities()
    labelled = cases()
    by_policy: dict[str, list[dict[str, Any]]] = {
        p: run_policy(p, caps) for p in POLICIES
    }
    tables = {
        p: per_capability_table(labelled, by_policy[p]) for p in POLICIES
    }
    macros = {p: macro_recall(tables[p]) for p in POLICIES}
    micros = {p: micro_recall(tables[p]) for p in POLICIES}
    overclaims = {
        p: overclaim_hidden_zero(tables[p], micros[p]) for p in POLICIES
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
                    "budget_spent": int(pred["token_cost"]),
                    "stage_count": wf["stage_count"],
                    "passed": bool(pred["passed"]),
                    "predicted": pred["capability_id"],
                    "expected": case["expected"],
                }
            )

    workflows = []
    for policy, wf in WORKFLOWS.items():
        preds = by_policy[policy]
        spent = [int(p["token_cost"]) for p in preds]
        workflows.append(
            {
                "id": wf["id"],
                "role": wf["role"],
                "stage_count": wf["stage_count"],
                "budget_limit": wf["budget_limit"],
                "budget_spent_mean": (sum(spent) / len(spent)) if spent else 0.0,
                "pass_rate": (sum(1 for p in preds if p["passed"]) / len(preds))
                if preds
                else 0.0,
                "macro_recall": macros[policy],
                "micro_recall": micros[policy],
            }
        )

    fusion_preds = {p["case_id"]: p for p in by_policy["full"]}
    regressions = []
    for src_policy in ("usage-pruned", "popularity-greedy"):
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

    fusion_worse = [
        r
        for r in regressions
        if r["fusion_score"] < r["source_score"]
    ]
    fusion_macro = macros["full"]
    source_macros = [macros["usage-pruned"], macros["popularity-greedy"]]
    outperforms = fusion_macro > max(source_macros) + 1e-9

    rare_rows = [
        p
        for p in by_policy["full"]
        if p["expected"] in RARE_IDS
    ]
    rare_selected = all(p["passed"] for p in rare_rows) and len(rare_rows) >= 2

    neg_rows = [p for p in by_policy["full"] if p["kind"] == "negative"]
    neg_ok = all(
        p["capability_id"] == FALLBACK_ID and p["confident"] is False
        for p in neg_rows
    ) and len(neg_rows) >= 2

    greedy_neg = [p for p in by_policy["popularity-greedy"] if p["kind"] == "negative"]
    greedy_confident_wrong = all(
        p["confident"] is True and p["capability_id"] != FALLBACK_ID
        for p in greedy_neg
    )

    per_cap_reported = all(
        cid in tables["full"]
        for cid in {c["expected"] for c in labelled}
    )
    fusion_zeros = zero_recall_capabilities(tables["full"])
    pruned_zeros = zero_recall_capabilities(tables["usage-pruned"])

    tests = {
        "test_recall_reported_per_capability_not_only_in_aggregate": (
            per_cap_reported
            and len(tables["full"]) >= 6
            and "micro_recall" in {"micro_recall"}
            and macros["full"] is not None
        ),
        "test_a_rarely_used_but_correct_skill_is_selected": rare_selected,
        "test_negative_control_fallback_not_confident_wrong_pick": neg_ok,
        "test_usage_pruned_hides_zero_recall_in_aggregate": (
            overclaims["usage-pruned"]["hidden_zero_recall"] is True
            and set(pruned_zeros) >= RARE_IDS
        ),
        "test_greedy_is_confident_wrong_on_negatives": greedy_confident_wrong,
        "test_fusion_has_no_hidden_zero": (
            not fusion_zeros and overclaims["full"]["hidden_zero_recall"] is False
        ),
    }

    mutant_caps = [c for c in caps if c["id"] != "skill.nul-device-census"]
    mutant_preds = run_policy("full", mutant_caps)
    mutant_table = per_capability_table(labelled, mutant_preds)
    mutant_nul = mutant_table.get("skill.nul-device-census") or {}
    tests["test_mutation_drop_rare_skill_turns_red"] = (
        mutant_nul.get("gold", 0) >= 1 and mutant_nul.get("recall") == 0
    )

    return {
        "policies": by_policy,
        "tables": tables,
        "macros": macros,
        "micros": micros,
        "overclaims": overclaims,
        "cells": cells,
        "workflows": workflows,
        "regressions": regressions,
        "fusion_worse": fusion_worse,
        "outperforms": outperforms,
        "tests": tests,
        "rare_selected": rare_selected,
        "neg_ok": neg_ok,
        "fusion_zeros": fusion_zeros,
        "pruned_zeros": pruned_zeros,
        "labelled": labelled,
        "repertoire": caps,
    }
