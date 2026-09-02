#!/usr/bin/env python3
"""Fusion admission gate for TST-0233.

A fused candidate is accepted only when it beats or materially complements
EVERY source on matched cases. Stage count is reported and is never a scoring
component: a fusion with identical per-case behaviour and more stages is
rejected (spec 11170 / FC-11334). A fusion whose matched score is strictly
below every source is rejected as the named class FC-11333.

Complementarity is a computed set of named cases where a source fails and the
fusion succeeds, not prose.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

FAILURE_MORE_STAGES = "fusion accepted because it has more stages (catalog gloss thin)"
FAILURE_MORE_STAGES_ID = "FC-11334"
SPEC_MORE_STAGES = 11170

FAILURE_WORSE = "fused workflow performs worse than every source"
FAILURE_WORSE_ID = "FC-11333"
SPEC_WORSE = 11333

MIN_PAYLOAD = 8
DEFAULT_BUDGET = 16


def load_corpus(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def index_workflows(corpus: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in corpus.get("workflows") or []:
        if isinstance(item, Mapping) and item.get("id"):
            out[str(item["id"])] = dict(item)
    return out


def resolve_sources(
    fusion: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for token in fusion.get("sources") or []:
        if isinstance(token, Mapping):
            resolved.append(dict(token))
            continue
        key = str(token)
        if key not in catalog:
            raise KeyError(f"unknown source {key!r} for fusion {fusion.get('id')!r}")
        resolved.append(dict(catalog[key]))
    return resolved


def stage_count(workflow: Mapping[str, Any]) -> int:
    stages = workflow.get("stages") or []
    return len(stages) if isinstance(stages, list) else 0


def plant_noop_stages(workflow: Mapping[str, Any], n: int = 3) -> dict[str, Any]:
    """Copy `workflow` with `n` trailing noop stages. Behaviour must stay identical."""
    if n < 1:
        raise ValueError("n must be >= 1")
    wf = copy.deepcopy(dict(workflow))
    stages = list(wf.get("stages") or [])
    base = str(wf.get("id") or "wf")
    for i in range(n):
        stages.append({"id": f"pad-{i}", "noop": True, "cost": 1})
    wf["stages"] = stages
    wf["kind"] = "fusion"
    wf["id"] = f"{base}.padded"
    if not wf.get("sources"):
        wf["sources"] = [base]
    return wf


def execute(
    workflow: Mapping[str, Any],
    case: Mapping[str, Any],
    budget: int,
) -> dict[str, Any]:
    """Run one workflow on one case under a declared budget.

    A non-noop stage whose `handles` list contains the case family solves the
    case iff the payload meets MIN_PAYLOAD. Noop stages consume budget and do
    not change the pass/fail bit. Score is never derived from stage count.
    """
    allocated = int(budget)
    remaining = allocated
    visited: list[str] = []
    payload = str(case.get("payload") or "")
    family = str(case.get("family") or "")
    n_stages = stage_count(workflow)

    def record(*, passed: bool, reason: str, handler: str | None = None, evidence: str = "") -> dict[str, Any]:
        return {
            "workflow_id": workflow.get("id"),
            "case_id": case.get("id"),
            "family": family,
            "passed": passed,
            "reason": reason,
            "handler": handler,
            "evidence": evidence,
            "budget_allocated": allocated,
            "budget_remaining": remaining,
            "stages_visited": list(visited),
            "n_stages": n_stages,
        }

    stages = workflow.get("stages") or []
    if not isinstance(stages, list):
        return record(passed=False, reason="malformed-stages")

    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        cost = int(stage.get("cost", 1))
        remaining -= cost
        visited.append(str(stage.get("id")))
        if remaining < 0:
            return record(passed=False, reason="budget-exhausted")
        if stage.get("noop") is True:
            continue
        handles = [str(x) for x in (stage.get("handles") or [])]
        if family and family in handles:
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if len(payload) < MIN_PAYLOAD:
                return record(
                    passed=False,
                    reason="payload-below-floor",
                    handler=str(stage.get("id")),
                    evidence=digest[:16],
                )
            return record(
                passed=True,
                reason="handled",
                handler=str(stage.get("id")),
                evidence=digest[:16],
            )
    return record(passed=False, reason="unhandled")


def score_from_runs(runs: Iterable[Mapping[str, Any]]) -> int:
    """Passed-case count. Stage count is excluded by construction."""
    return sum(1 for r in runs if r.get("passed") is True)


def outcome_vector(runs: list[Mapping[str, Any]]) -> tuple[tuple[str, bool], ...]:
    return tuple((str(r.get("case_id")), bool(r.get("passed"))) for r in runs)


def run_workflow(
    workflow: Mapping[str, Any],
    cases: Iterable[Mapping[str, Any]],
    budget: int,
) -> dict[str, Any]:
    case_list = [c for c in cases if isinstance(c, Mapping)]
    runs = [execute(workflow, case, budget) for case in case_list]
    passed = score_from_runs(runs)
    n = len(runs)
    budgets = {int(r["budget_allocated"]) for r in runs}
    return {
        "workflow_id": workflow.get("id"),
        "kind": workflow.get("kind"),
        "n_stages": stage_count(workflow),
        "n_cases": n,
        "passed": passed,
        "failed": n - passed,
        "score": passed,
        "score_formula": "passed_cases",
        "vanity_excluded": "n_stages",
        "budget_allocated": budget,
        "budget_parity": len(budgets) == 1 and budget in budgets,
        "outcome_vector": [[cid, ok] for cid, ok in outcome_vector(runs)],
        "runs": runs,
    }


def complementarity_cases(
    fusion_row: Mapping[str, Any],
    source_row: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Named cases where the source fails and the fusion succeeds."""
    fused = {str(cid): bool(ok) for cid, ok in fusion_row.get("outcome_vector") or []}
    src = {str(cid): bool(ok) for cid, ok in source_row.get("outcome_vector") or []}
    out: list[dict[str, Any]] = []
    for cid, src_ok in src.items():
        if src_ok is False and fused.get(cid) is True:
            out.append(
                {
                    "case_id": cid,
                    "source_id": source_row.get("workflow_id"),
                    "fusion_id": fusion_row.get("workflow_id"),
                    "source_passed": False,
                    "fusion_passed": True,
                }
            )
    return out


def detect_stage_padding(
    fusion_row: Mapping[str, Any],
    source_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    fused_vec = [tuple(x) for x in (fusion_row.get("outcome_vector") or [])]
    matches: list[dict[str, Any]] = []
    for src in source_rows:
        src_vec = [tuple(x) for x in (src.get("outcome_vector") or [])]
        more = int(fusion_row.get("n_stages") or 0) > int(src.get("n_stages") or 0)
        identical = fused_vec == src_vec
        if identical and more:
            matches.append(
                {
                    "source_id": src.get("workflow_id"),
                    "source_stages": src.get("n_stages"),
                    "fusion_stages": fusion_row.get("n_stages"),
                    "identical_behavior": True,
                }
            )
    fired = bool(matches)
    return {
        "fired": fired,
        "matches": matches,
        "failure_class": FAILURE_MORE_STAGES if fired else None,
        "failure_class_id": FAILURE_MORE_STAGES_ID if fired else None,
        "spec": SPEC_MORE_STAGES,
    }


def detect_worse_than_every_source(
    fusion_row: Mapping[str, Any],
    source_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    src_list = list(source_rows)
    fscore = int(fusion_row.get("score") or 0)
    source_scores = [
        {"source_id": s.get("workflow_id"), "score": int(s.get("score") or 0)}
        for s in src_list
    ]
    fired = bool(src_list) and all(fscore < int(s.get("score") or 0) for s in src_list)
    return {
        "fired": fired,
        "fusion_score": fscore,
        "source_scores": source_scores,
        "failure_class": FAILURE_WORSE if fired else None,
        "failure_class_id": FAILURE_WORSE_ID if fired else None,
        "spec": SPEC_WORSE,
    }


def per_source_beat_or_complement(
    fusion_row: Mapping[str, Any],
    source_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fscore = int(fusion_row.get("score") or 0)
    for src in source_rows:
        sscore = int(src.get("score") or 0)
        comps = complementarity_cases(fusion_row, src)
        beats = fscore > sscore
        rows.append(
            {
                "source_id": src.get("workflow_id"),
                "source_score": sscore,
                "fusion_score": fscore,
                "beats": beats,
                "complements": bool(comps),
                "complement_cases": comps,
                "qualifies": beats or bool(comps),
            }
        )
    return rows


def evaluate_admission(
    fusion: Mapping[str, Any],
    sources: Iterable[Mapping[str, Any]],
    cases: Iterable[Mapping[str, Any]],
    budget: int,
) -> dict[str, Any]:
    src_list = [s for s in sources if isinstance(s, Mapping)]
    case_list = [c for c in cases if isinstance(c, Mapping)]
    fusion_row = run_workflow(fusion, case_list, budget)
    source_rows = [run_workflow(s, case_list, budget) for s in src_list]
    padding = detect_stage_padding(fusion_row, source_rows)
    worse = detect_worse_than_every_source(fusion_row, source_rows)
    per_source = per_source_beat_or_complement(fusion_row, source_rows)
    budgets = [fusion_row["budget_allocated"]] + [r["budget_allocated"] for r in source_rows]
    budget_parity = len(set(budgets)) == 1

    reasons: list[str] = []
    failure_class = None
    failure_class_id = None
    spec = None
    if padding["fired"]:
        reasons.append("stage-padded-identical-behavior")
        failure_class = FAILURE_MORE_STAGES
        failure_class_id = FAILURE_MORE_STAGES_ID
        spec = SPEC_MORE_STAGES
        verdict = "REJECT"
    elif worse["fired"]:
        reasons.append("worse-than-every-source")
        failure_class = FAILURE_WORSE
        failure_class_id = FAILURE_WORSE_ID
        spec = SPEC_WORSE
        verdict = "REJECT"
    elif not per_source:
        reasons.append("no-sources")
        verdict = "REJECT"
    elif not all(r["qualifies"] for r in per_source):
        reasons.append("does-not-beat-or-complement-every-source")
        verdict = "REJECT"
    elif not budget_parity:
        reasons.append("budget-asymmetry")
        verdict = "REJECT"
    else:
        reasons.append("beats-or-complements-every-source")
        verdict = "ACCEPT"

    named_complements = []
    for row in per_source:
        named_complements.extend(row["complement_cases"])

    return {
        "fusion_id": fusion.get("id"),
        "source_ids": [s.get("id") for s in src_list],
        "verdict": verdict,
        "reasons": reasons,
        "failure_class": failure_class,
        "failure_class_id": failure_class_id,
        "spec": spec,
        "budget": budget,
        "budget_parity": budget_parity,
        "score_formula": "passed_cases",
        "stage_count_is_scoring_component": False,
        "padding": padding,
        "worse_than_sources": worse,
        "per_source": per_source,
        "named_complement_cases": named_complements,
        "fusion": fusion_row,
        "sources": source_rows,
        "matrix": {
            fusion_row["workflow_id"]: {
                "passed": fusion_row["passed"],
                "score": fusion_row["score"],
                "n_stages": fusion_row["n_stages"],
                "outcome_vector": fusion_row["outcome_vector"],
            },
            **{
                r["workflow_id"]: {
                    "passed": r["passed"],
                    "score": r["score"],
                    "n_stages": r["n_stages"],
                    "outcome_vector": r["outcome_vector"],
                }
                for r in source_rows
            },
        },
    }


def evaluate_named(
    corpus: Mapping[str, Any], fusion_id: str, budget: int | None = None
) -> dict[str, Any]:
    catalog = index_workflows(corpus)
    fusion = catalog[fusion_id]
    sources = resolve_sources(fusion, catalog)
    used_budget = int(budget if budget is not None else corpus.get("budget") or DEFAULT_BUDGET)
    return evaluate_admission(fusion, sources, corpus.get("cases") or [], used_budget)
