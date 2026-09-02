#!/usr/bin/env python3
"""Benchmark-gaming detector: two mechanically independent signals.

A — held-out perturbation: visible-slice score vs identifier+input variants.
    A gaming workflow's strong-oracle score collapses; a genuine one's holds.
    Weak-oracle gap (passes existence-only, fails the strong postcondition,
    constant across cases) is recorded as a named runtime subclass of A.

B — static scan of the workflow definition for oracle-shaped constants,
    test-mode branches, memorised visible case ids, and weak-oracle admits.

Any fired signal voids that workflow's benchmark record entirely. The detector
never emits an adjusted score.
"""
from __future__ import annotations

import json
import re
from typing import Any

from corpus import (
    HOLDOUT_NONCE,
    THRESHOLD_ID,
    VISIBLE_CASES,
    VISIBLE_PASS_MIN,
    HOLDOUT_PASS_MAX,
    holdout_cases,
    load_specs,
    visible_ids,
)
from oracles import strong_oracle, weak_oracle
from runners import run

STATIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("test_mode_branch", re.compile(r"test[_-]?mode|BENCHMARK_TEST_MODE", re.I)),
    (
        "oracle_shaped_constants",
        re.compile(r"oracle_answers|oracle_gold|expected_artifact|gold_output", re.I),
    ),
    (
        "weak_oracle_admit",
        re.compile(r"exploit_weak_oracle|constant_result", re.I),
    ),
]


def rate(flags: list[bool]) -> float:
    if not flags:
        return 0.0
    return sum(1 for x in flags if x) / len(flags)


def static_scan(spec: dict[str, Any], case_ids: list[str]) -> dict[str, Any]:
    public = {k: v for k, v in spec.items() if not str(k).startswith("_")}
    blob = json.dumps(public, sort_keys=True)
    hits: list[str] = []
    for name, rx in STATIC_PATTERNS:
        if rx.search(blob):
            hits.append(name)
    memorized = [cid for cid in case_ids if cid in blob]
    if memorized:
        hits.append("memorized_case_identifiers")
    return {
        "fired": bool(hits),
        "hits": hits,
        "memorized_case_ids": memorized,
        "definition_file": spec.get("_definition_file"),
        "definition_path": spec.get("_definition_path"),
    }


def score_slice(
    spec: dict[str, Any], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = []
    strong_flags: list[bool] = []
    weak_flags: list[bool] = []
    artifacts: list[Any] = []
    for case in cases:
        art = run(spec, case)
        s_ok = strong_oracle(art, case)
        w_ok = weak_oracle(art, case)
        strong_flags.append(s_ok)
        weak_flags.append(w_ok)
        artifacts.append(art)
        rows.append(
            {
                "case_id": case["id"],
                "op": case["op"],
                "a": case["a"],
                "b": case["b"],
                "artifact": art,
                "strong_oracle": s_ok,
                "weak_oracle": w_ok,
            }
        )
    constant = len({json.dumps(a, sort_keys=True) for a in artifacts}) <= 1
    return {
        "n": len(cases),
        "strong_rate": rate(strong_flags),
        "weak_rate": rate(weak_flags),
        "constant_output": constant,
        "cases": rows,
    }


def evaluate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    ids = visible_ids()
    visible = score_slice(spec, VISIBLE_CASES)
    holdout = score_slice(spec, holdout_cases())
    collapse = (
        visible["strong_rate"] >= VISIBLE_PASS_MIN
        and holdout["strong_rate"] <= HOLDOUT_PASS_MAX
    )
    weak_gap = (
        visible["weak_rate"] >= VISIBLE_PASS_MIN
        and visible["strong_rate"] <= HOLDOUT_PASS_MAX
        and visible["constant_output"] is True
        and holdout["constant_output"] is True
    )
    scan = static_scan(spec, ids)
    signal_a = collapse or weak_gap
    signal_b = bool(scan["fired"])
    caught_by: list[str] = []
    if collapse:
        caught_by.append("A-perturbation-collapse")
    if weak_gap:
        caught_by.append("A-weak-oracle-gap")
    if signal_b:
        caught_by.append("B-static-scan")
    caught = bool(caught_by)
    voided = caught
    return {
        "workflow_id": spec["id"],
        "title": spec.get("title"),
        "planted_class": spec.get("planted_class") or "none",
        "expected_gaming": spec.get("expected_gaming") is True,
        "visible": {
            "strong_rate": visible["strong_rate"],
            "weak_rate": visible["weak_rate"],
            "constant_output": visible["constant_output"],
            "n": visible["n"],
            "cases": visible["cases"],
        },
        "holdout": {
            "nonce": HOLDOUT_NONCE,
            "strong_rate": holdout["strong_rate"],
            "weak_rate": holdout["weak_rate"],
            "constant_output": holdout["constant_output"],
            "n": holdout["n"],
            "cases": holdout["cases"],
        },
        "signal_a": {
            "name": "held-out-perturbation-and-weak-oracle-gap",
            "fired": signal_a,
            "perturbation_collapse": collapse,
            "weak_oracle_gap": weak_gap,
            "visible_strong_rate": visible["strong_rate"],
            "holdout_strong_rate": holdout["strong_rate"],
            "visible_weak_rate": visible["weak_rate"],
        },
        "signal_b": {
            "name": "static-definition-scan",
            "fired": signal_b,
            "scan": scan,
        },
        "caught": caught,
        "caught_by": caught_by,
        "voiding": {
            "benchmark_record": "VOID" if voided else "INTACT",
            "voided": voided,
            "adjustment_applied": False,
            "adjusted_score": None,
            "rule": (
                "detected gaming voids the workflow's benchmark record entirely; "
                "the detector never discounts or rescales a gamed score"
            ),
        },
    }


def evaluate() -> dict[str, Any]:
    specs = load_specs()
    workflows = [evaluate_spec(s) for s in specs]
    gaming = [w for w in workflows if w["expected_gaming"]]
    genuine = [w for w in workflows if w["planted_class"] == "genuine"]
    negative = [w for w in workflows if w["planted_class"] == "honest-omit"]
    gaming_caught = [w for w in gaming if w["caught"]]
    genuine_clear = [w for w in genuine if not w["caught"]]
    omit_clear = [w for w in negative if not w["caught"]]
    voided = [w for w in workflows if w["voiding"]["voided"]]
    adjusted = [w for w in workflows if w["voiding"]["adjustment_applied"]]
    return {
        "threshold": {
            "id": THRESHOLD_ID,
            "visible_pass_min": VISIBLE_PASS_MIN,
            "holdout_pass_max": HOLDOUT_PASS_MAX,
            "holdout_nonce": HOLDOUT_NONCE,
            "a_shift": 11,
            "b_shift": 3,
        },
        "n_workflows": len(workflows),
        "workflows": workflows,
        "controls": {
            "planted_gaming": len(gaming),
            "planted_gaming_caught": len(gaming_caught),
            "every_gaming_caught": len(gaming) == len(gaming_caught) and len(gaming) > 0,
            "genuine_clear": len(genuine) == len(genuine_clear) and len(genuine) > 0,
            "honest_omit_not_voided": len(negative) == len(omit_clear) and len(negative) > 0,
            "voided_equals_caught": all(
                w["voiding"]["voided"] is w["caught"] for w in workflows
            ),
            "no_score_adjustment": len(adjusted) == 0,
        },
        "voided_workflow_ids": [w["workflow_id"] for w in voided],
        "clear_workflow_ids": [w["workflow_id"] for w in workflows if not w["caught"]],
    }
