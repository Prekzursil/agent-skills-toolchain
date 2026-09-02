#!/usr/bin/env python3
"""Superiority gate: equal budget, stage counts, per-case regressions, unearned stages.

Spec line 11170: a merged workflow is not accepted because it contains more stages.
Unearned stages are those whose ablation leaves the score vector unchanged.
"""
from __future__ import annotations

import copy

from harness import (
    FUSION,
    SOURCE_RETRIEVE,
    SOURCE_TRANSFORM,
    execute_case,
    pass_rate,
    run_matrix,
    score_vector,
    stage_count,
)


def per_case_regressions(matrix: dict, fusion_id: str, source_ids: list[str]) -> list[dict]:
    ids = [c["id"] for c in matrix["cases"]]
    out: list[dict] = []
    fusion_scores = matrix["by_workflow"][fusion_id]
    for case_id in ids:
        f = fusion_scores[case_id]
        for sid in source_ids:
            s = matrix["by_workflow"][sid][case_id]
            if f < s:
                out.append(
                    {
                        "case_id": case_id,
                        "source_id": sid,
                        "fusion_score": f,
                        "source_score": s,
                    }
                )
    return out


def complementary_cases(matrix: dict, fusion_id: str, source_ids: list[str]) -> list[str]:
    ids = [c["id"] for c in matrix["cases"]]
    found = []
    for case_id in ids:
        if matrix["by_workflow"][fusion_id][case_id] <= 0:
            continue
        if all(matrix["by_workflow"][s][case_id] == 0 for s in source_ids):
            found.append(case_id)
    return found


def unearned_stages(workflow: dict, cases, budget_limit: int) -> list[str]:
    """Stages that can be removed without changing the per-case score vector."""
    stages = list(workflow.get("stages") or [])
    if len(stages) < 2:
        return []
    base = tuple(
        execute_case(workflow, case, budget_limit=budget_limit)["score"] for case in cases
    )
    unearned: list[str] = []
    for i, stage in enumerate(stages):
        stripped = copy.deepcopy(workflow)
        stripped["stages"] = [s for j, s in enumerate(stages) if j != i]
        vec = tuple(
            execute_case(stripped, case, budget_limit=budget_limit)["score"]
            for case in cases
        )
        if vec == base:
            unearned.append(str(stage.get("id") or f"stage-{i}"))
    return unearned


def decide(
    matrix: dict,
    fusion: dict,
    sources: list[dict],
    cases,
    budget_limit: int,
) -> dict:
    fusion_id = fusion["id"]
    source_ids = [s["id"] for s in sources]
    parity = bool(matrix["budget_parity"]["equal"])
    if not parity:
        return {
            "verdict": "REFUSED",
            "classification": "budget-asymmetry",
            "reason": "budget limits differ across arms; comparison is not matched",
            "outperforms_every_source": False,
            "merely_adds_stages": False,
            "regresses_on_any_case": False,
            "per_case_regressions": [],
            "complementary_cases": [],
            "unearned_stages": [],
            "fusion_pass_rate": None,
            "source_pass_rates": {s: None for s in source_ids},
        }

    f_rate = pass_rate(matrix, fusion_id)
    source_rates = {s: pass_rate(matrix, s) for s in source_ids}
    outperforms = all(f_rate > r for r in source_rates.values())
    regs = per_case_regressions(matrix, fusion_id, source_ids)
    comps = complementary_cases(matrix, fusion_id, source_ids)
    unearned = unearned_stages(fusion, cases, budget_limit)
    merely = bool(unearned) and stage_count(fusion) > max(stage_count(s) for s in sources)

    if merely:
        verdict = "REJECT"
        classification = "unearned-fusion"
        reason = (
            "fusion has more stages than its sources and at least one stage can be "
            "ablated without changing the score vector (spec 11170)"
        )
    elif outperforms:
        verdict = "ACCEPT"
        classification = None
        reason = "fusion pass_rate exceeds every source at equal budget"
    elif comps:
        verdict = "ACCEPT-COMPLEMENTARY"
        classification = None
        reason = (
            "fusion does not beat every source on the aggregate metric but passes "
            "at least one case every source fails"
        )
    else:
        verdict = "REJECT"
        classification = "unearned-fusion"
        reason = "fusion neither outperforms every source nor supplies a complementary case"

    if not merely and regs and verdict in {"ACCEPT", "ACCEPT-COMPLEMENTARY"}:
        # Aggregate may still improve; regressions are reported, never dropped.
        classification = classification or "per-case-regression"

    return {
        "verdict": verdict,
        "classification": classification,
        "reason": reason,
        "outperforms_every_source": outperforms,
        "merely_adds_stages": merely,
        "regresses_on_any_case": bool(regs),
        "per_case_regressions": regs,
        "complementary_cases": comps,
        "unearned_stages": unearned,
        "fusion_pass_rate": f_rate,
        "source_pass_rates": source_rates,
        "fusion_stage_count": stage_count(fusion),
        "source_stage_counts": {s["id"]: stage_count(s) for s in sources},
        "score_vectors": {
            fusion_id: list(score_vector(matrix, fusion_id)),
            **{s: list(score_vector(matrix, s)) for s in source_ids},
        },
    }


def measure_subject(fusion, sources, cases, budget_limit: int, budget_limits=None) -> dict:
    matrix = run_matrix(
        sources + [fusion],
        cases=cases,
        budget_limit=budget_limit,
        budget_limits=budget_limits,
    )
    gate = decide(matrix, fusion, sources, cases, budget_limit)
    return {"matrix": matrix, "gate": gate}


def detector_controls(cases, budget_limit: int) -> dict:
    from harness import (
        fusion_degraded,
        fusion_per_case_regression,
        fusion_stage_padded,
        fusion_union,
        source_retrieve,
        source_transform,
    )

    sources = [source_retrieve(), source_transform()]
    good = measure_subject(fusion_union(), sources, cases, budget_limit)
    padded = measure_subject(fusion_stage_padded(), sources, cases, budget_limit)
    degraded = measure_subject(fusion_degraded(), sources, cases, budget_limit)
    regress = measure_subject(fusion_per_case_regression(), sources, cases, budget_limit)
    asymmetric = measure_subject(
        fusion_union(),
        sources,
        cases,
        budget_limit,
        budget_limits={
            FUSION: budget_limit,
            SOURCE_RETRIEVE: 1,
            SOURCE_TRANSFORM: 1,
        },
    )
    return {
        "good": {
            "verdict": good["gate"]["verdict"],
            "merely_adds_stages": good["gate"]["merely_adds_stages"],
            "regresses_on_any_case": good["gate"]["regresses_on_any_case"],
            "outperforms_every_source": good["gate"]["outperforms_every_source"],
            "unearned_stages": good["gate"]["unearned_stages"],
            "pass": good["gate"]["verdict"] == "ACCEPT"
            and not good["gate"]["merely_adds_stages"]
            and not good["gate"]["regresses_on_any_case"],
        },
        "stage_padded": {
            "verdict": padded["gate"]["verdict"],
            "classification": padded["gate"]["classification"],
            "unearned_stages": padded["gate"]["unearned_stages"],
            "pass": padded["gate"]["verdict"] == "REJECT"
            and padded["gate"]["classification"] == "unearned-fusion"
            and bool(padded["gate"]["unearned_stages"]),
        },
        "degraded": {
            "verdict": degraded["gate"]["verdict"],
            "classification": degraded["gate"]["classification"],
            "outperforms_every_source": degraded["gate"]["outperforms_every_source"],
            "pass": degraded["gate"]["verdict"] == "REJECT"
            and not degraded["gate"]["outperforms_every_source"],
        },
        "per_case_regression": {
            "verdict": regress["gate"]["verdict"],
            "regresses_on_any_case": regress["gate"]["regresses_on_any_case"],
            "outperforms_every_source": regress["gate"]["outperforms_every_source"],
            "regressions": regress["gate"]["per_case_regressions"],
            "pass": regress["gate"]["regresses_on_any_case"]
            and regress["gate"]["outperforms_every_source"]
            and any(
                r["case_id"] == "case.lookup.b" and r["source_id"] == SOURCE_RETRIEVE
                for r in regress["gate"]["per_case_regressions"]
            ),
        },
        "budget_asymmetric": {
            "verdict": asymmetric["gate"]["verdict"],
            "classification": asymmetric["gate"]["classification"],
            "equal": asymmetric["matrix"]["budget_parity"]["equal"],
            "pass": asymmetric["gate"]["verdict"] == "REFUSED"
            and asymmetric["gate"]["classification"] == "budget-asymmetry"
            and asymmetric["matrix"]["budget_parity"]["equal"] is False,
        },
    }


def controls_pass(ctrl: dict) -> bool:
    return all(ctrl[k]["pass"] for k in ctrl)
