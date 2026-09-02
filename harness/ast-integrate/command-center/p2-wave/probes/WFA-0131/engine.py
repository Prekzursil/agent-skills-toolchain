#!/usr/bin/env python3
"""Naive four-metric scorer plus gaming-control-v1.

Naive scores use the visible slice only (the leak the attacks exploit).
The counter-control uses held-out correctness, effort surplus, and a
capability assertion. Thresholds come from the pinned registry.
"""
from __future__ import annotations

from typing import Any

from corpus import CASES, OUTPUT_FIELDS, REQUIRED_CAPABILITIES
from registry import load_pinned_registry

METRIC_NAMES = ("correctness", "coverage", "recovery", "usability")


def _round(x: float) -> float:
    return round(float(x), 6)


def _rows_for(trace: list[dict], slice_name: str) -> list[dict]:
    rows = [r for r in trace if r.get("slice") == slice_name]
    if not rows:
        raise ValueError(f"empty slice {slice_name!r}")
    return rows


def correctness(trace: list[dict], slice_name: str) -> float:
    rows = _rows_for(trace, slice_name)
    return _round(sum(1 for r in rows if r["correct"]) / len(rows))


def coverage(trace: list[dict], slice_name: str) -> float:
    rows = _rows_for(trace, slice_name)
    declared: set[str] = set()
    for r in rows:
        for cap in r.get("declared_capabilities") or []:
            declared.add(str(cap))
    required = set(REQUIRED_CAPABILITIES)
    return _round(len(declared & required) / len(required))


def recovery(trace: list[dict], slice_name: str) -> float:
    rows = _rows_for(trace, slice_name)
    first_fail = [r for r in rows if r.get("first_failed")]
    if not first_fail:
        return 1.0 if all(r["correct"] for r in rows) else 0.0
    recovered = 0
    for r in first_fail:
        if r["correct"] or r.get("claimed_recovered"):
            recovered += 1
    return _round(recovered / len(first_fail))


def usability(trace: list[dict], slice_name: str) -> float:
    rows = _rows_for(trace, slice_name)
    n_fields = len(OUTPUT_FIELDS)
    total = 0.0
    for r in rows:
        present = int(r.get("fields_present") or 0)
        required = int(r.get("fields_required") or n_fields)
        total += present / required if required else 0.0
    return _round(total / len(rows))


def metrics_for(trace: list[dict], slice_name: str) -> dict[str, float]:
    return {
        "correctness": correctness(trace, slice_name),
        "coverage": coverage(trace, slice_name),
        "recovery": recovery(trace, slice_name),
        "usability": usability(trace, slice_name),
    }


def composite(mets: dict[str, float], registry: dict) -> float:
    acc = 0.0
    for name in METRIC_NAMES:
        weight = float(registry["metrics"][name]["weight"])
        acc += weight * float(mets[name])
    return _round(acc)


def naive_accept(candidate: dict[str, float], baseline: dict[str, float], registry: dict) -> dict:
    delta = _round(candidate["composite"] - baseline["composite"])
    min_effect = float(registry["min_effect_size"])
    max_reg = float(registry["max_single_metric_regression"])
    regressions = []
    for name in METRIC_NAMES:
        drop = _round(float(baseline[name]) - float(candidate[name]))
        if drop > max_reg:
            regressions.append({"metric": name, "drop": drop})
    ok = delta >= min_effect and not regressions
    return {
        "decision": "ACCEPT" if ok else "REJECT",
        "composite_delta": delta,
        "min_effect_size": min_effect,
        "regressions": regressions,
    }


def effort_surplus(trace: list[dict], slice_name: str = "visible") -> dict[str, float]:
    rows = _rows_for(trace, slice_name)
    mean_attempts = sum(int(r.get("attempts") or 1) for r in rows) / len(rows)
    max_stages = max(int(r.get("stages") or 1) for r in rows)
    surplus_attempts = max(0.0, mean_attempts - 1.0)
    surplus_stages = max(0.0, float(max_stages - 1))
    return {
        "mean_attempts": _round(mean_attempts),
        "max_stages": float(max_stages),
        "surplus_attempts": _round(surplus_attempts),
        "surplus_stages": _round(surplus_stages),
        "extra_effort": _round(surplus_attempts + surplus_stages),
    }


def actual_heldout_capability_rate(trace: list[dict]) -> float:
    solved: set[str] = set()
    for r in _rows_for(trace, "held-out"):
        if r["correct"]:
            solved.add(str(r["capability"]))
    return _round(len(solved & set(REQUIRED_CAPABILITIES)) / len(REQUIRED_CAPABILITIES))


def evaluate_control(
    trace: list[dict], baseline_trace: list[dict], registry: dict
) -> dict[str, Any]:
    ctl = registry["counter_control"]
    vis_c = correctness(trace, "visible")
    ho_c = correctness(trace, "held-out")
    base_ho = correctness(baseline_trace, "held-out")
    gap = _round(vis_c - ho_c)
    ho_gain = _round(ho_c - base_ho)
    eff = effort_surplus(trace, "visible")
    claimed_cov = coverage(trace, "visible")
    actual_ho_caps = actual_heldout_capability_rate(trace)
    cap_gap = _round(claimed_cov - actual_ho_caps)
    usa = usability(trace, "visible")
    shape_gap = _round(usa - ho_c)
    fires: list[str] = []
    if gap > float(ctl["held_out_gap_max"]):
        fires.append("held-out-gap")
    if (
        eff["extra_effort"] > float(ctl["effort_surplus_min"])
        and ho_gain <= float(ctl["held_out_gain_min"])
    ):
        fires.append("effort-without-capability")
    if cap_gap > float(ctl["claimed_vs_heldout_cap_gap_max"]):
        fires.append("capability-assertion")
    if shape_gap > float(ctl["usability_minus_heldout_correctness_max"]):
        fires.append("output-shaping")
    return {
        "id": ctl["id"],
        "verdict": "FIRE" if fires else "SILENT",
        "fires": fires,
        "visible_correctness": vis_c,
        "heldout_correctness": ho_c,
        "heldout_gap": gap,
        "heldout_gain_vs_baseline": ho_gain,
        "claimed_coverage": claimed_cov,
        "actual_heldout_capability_rate": actual_ho_caps,
        "capability_gap": cap_gap,
        "usability": usa,
        "shaping_gap": shape_gap,
        "effort": eff,
    }


def score_run(
    name: str,
    trace: list[dict],
    baseline_trace: list[dict],
    registry: dict,
) -> dict[str, Any]:
    naive_mets = metrics_for(trace, "visible")
    held_mets = metrics_for(trace, "held-out")
    naive_mets["composite"] = composite(naive_mets, registry)
    held_mets["composite"] = composite(held_mets, registry)
    base_naive = metrics_for(baseline_trace, "visible")
    base_naive["composite"] = composite(base_naive, registry)
    pred = naive_accept(naive_mets, base_naive, registry)
    control = evaluate_control(trace, baseline_trace, registry)
    gated = pred["decision"] == "ACCEPT" and control["verdict"] == "SILENT"
    return {
        "variant": name,
        "naive": naive_mets,
        "held_out": held_mets,
        "naive_predicate": pred,
        "control": control,
        "gated_decision": "ACCEPT" if gated else "REJECT",
        "trace_n": len(trace),
    }


def run_variant(fn, cases: list[dict] | None = None) -> list[dict]:
    rows = []
    for case in cases or CASES:
        row = fn(case)
        if not isinstance(row, dict):
            raise TypeError(f"variant returned {type(row)}")
        if row.get("case_id") != case["id"]:
            raise ValueError("variant case_id mismatch")
        rows.append(row)
    if len(rows) != len(cases or CASES):
        raise ValueError("variant dropped cases")
    return rows
