#!/usr/bin/env python3
"""Independent rubric recomputation from raw run records.

Blind to fusion-lane summaries. Do not load the sealed-lane scorer from here.
Scores are computed from recorded oracle_pass / cost_units / case_id only.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

# Weights apply only to components that can be computed from the records.
# Recovery is unmeasurable here (no retry events recorded) and is omitted,
# not zero-weighted — WFA-0114: a component that cannot be computed is removed.
WEIGHTS = {
    "correctness": 0.5,
    "coverage": 0.3,
    "usability": 0.2,
}


def _case_pass_map(rows: list[dict]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for r in rows:
        out[r["case_id"]] = bool(r["oracle_pass"])
    return out


def score_workflow(rows: list[dict], n_cases: int) -> dict[str, Any]:
    if not rows:
        return {
            "correctness": None,
            "coverage": None,
            "usability": None,
            "composite": None,
            "n_rows": 0,
            "unmeasurable": ["correctness", "coverage", "usability", "recovery"],
        }
    passes = [1.0 if r["oracle_pass"] else 0.0 for r in rows]
    correctness = sum(passes) / len(passes)
    coverage = sum(1 for r in rows if r["oracle_pass"]) / float(n_cases)
    usability = 1.0 - (
        sum(r["cost_units"] / float(r["budget"]) for r in rows) / len(rows)
    )
    composite = (
        WEIGHTS["correctness"] * correctness
        + WEIGHTS["coverage"] * coverage
        + WEIGHTS["usability"] * usability
    )
    return {
        "correctness": round(correctness, 6),
        "coverage": round(coverage, 6),
        "usability": round(usability, 6),
        "composite": round(composite, 6),
        "n_rows": len(rows),
        "n_pass": int(sum(passes)),
        "unmeasurable": ["recovery"],
        "recovery_omitted_reason": (
            "no retry/repair events in the raw records; component removed "
            "rather than weighted to zero"
        ),
        "formula": (
            "composite = 0.5*mean(oracle_pass) + 0.3*(n_pass/n_cases) + "
            "0.2*(1 - mean(cost/budget))"
        ),
    }


def complementarity(
    fused_rows: list[dict],
    source_rows_by_wf: dict[str, list[dict]],
) -> dict[str, Any]:
    """Cases the fusion passes that every source fails — measurable coverage delta."""
    fused_pass = _case_pass_map(fused_rows)
    source_pass: dict[str, dict[str, bool]] = {
        wf: _case_pass_map(rows) for wf, rows in source_rows_by_wf.items()
    }
    exclusive: list[str] = []
    for case_id, ok in fused_pass.items():
        if not ok:
            continue
        if all(not sp.get(case_id, False) for sp in source_pass.values()):
            exclusive.append(case_id)
    exclusive.sort()
    return {
        "cases_fusion_passes_sources_fail": exclusive,
        "delta": len(exclusive),
        "operationalised_as": "count of cases fusion passes and every source fails",
    }


def certify(
    fused_id: str,
    fused_score: dict,
    source_scores: dict[str, dict],
    floor: float,
    comp: dict,
    gaming: bool,
) -> dict[str, Any]:
    if gaming:
        return {
            "workflow_id": fused_id,
            "verdict": "VOID",
            "reason": "gaming detector fired; benchmark record voided, not adjusted",
        }
    fused_c = fused_score.get("composite")
    if fused_c is None:
        return {
            "workflow_id": fused_id,
            "verdict": "REFUTED",
            "reason": "insufficient evidence to score the fused arm",
        }
    source_c = {
        wf: sc["composite"]
        for wf, sc in source_scores.items()
        if sc.get("composite") is not None
    }
    if not source_c:
        return {
            "workflow_id": fused_id,
            "verdict": "REFUTED",
            "reason": "insufficient evidence to score source arms",
        }
    best = max(source_c.values())
    worst = min(source_c.values())
    advantage_vs_best = fused_c - best
    if comp["delta"] > 0 and advantage_vs_best >= -floor:
        return {
            "workflow_id": fused_id,
            "verdict": "PASS",
            "reason": (
                f"complementarity delta={comp['delta']} "
                f"(cases={comp['cases_fusion_passes_sources_fail']}) "
                f"with composite {fused_c} vs best source {best}, floor={floor}"
            ),
            "advantage_vs_best": round(advantage_vs_best, 6),
        }
    if advantage_vs_best > floor:
        return {
            "workflow_id": fused_id,
            "verdict": "PASS",
            "reason": (
                f"composite {fused_c} exceeds best source {best} by more than floor {floor}"
            ),
            "advantage_vs_best": round(advantage_vs_best, 6),
        }
    if fused_c + floor < worst:
        return {
            "workflow_id": fused_id,
            "verdict": "FAIL",
            "reason": (
                f"composite {fused_c} below ALL sources (worst={worst}) "
                f"by more than floor {floor}"
            ),
            "advantage_vs_best": round(advantage_vs_best, 6),
        }
    if abs(advantage_vs_best) <= floor:
        return {
            "workflow_id": fused_id,
            "verdict": "INCONCLUSIVE",
            "reason": (
                f"|composite-best|={abs(advantage_vs_best)} <= variance floor {floor}; "
                "inside-floor is not a pass"
            ),
            "advantage_vs_best": round(advantage_vs_best, 6),
        }
    return {
        "workflow_id": fused_id,
        "verdict": "FAIL",
        "reason": (
            f"composite {fused_c} does not beat best source {best} above floor "
            f"{floor} and complementarity delta={comp['delta']}"
        ),
        "advantage_vs_best": round(advantage_vs_best, 6),
    }


def recompute(
    records: list[dict],
    *,
    n_cases: int,
    source_ids: tuple[str, ...],
    fused_ids: tuple[str, ...],
    floor: float,
    gaming_hits: dict[str, bool],
) -> dict[str, Any]:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("control") == "same-workflow-twice":
            continue
        by[r["workflow_id"]].append(r)
    scores = {wf: score_workflow(rows, n_cases) for wf, rows in by.items()}
    source_scores = {wf: scores[wf] for wf in source_ids if wf in scores}
    source_rows = {wf: by[wf] for wf in source_ids if wf in by}
    verdicts = []
    comps = {}
    for fid in fused_ids:
        comp = complementarity(by.get(fid, []), source_rows)
        comps[fid] = comp
        verdicts.append(
            certify(
                fid,
                scores.get(fid, {}),
                source_scores,
                floor,
                comp,
                bool(gaming_hits.get(fid)),
            )
        )
    return {
        "scores": scores,
        "complementarity": comps,
        "verdicts": verdicts,
        "weights": dict(WEIGHTS),
        "read_fusion_summary": False,
    }
