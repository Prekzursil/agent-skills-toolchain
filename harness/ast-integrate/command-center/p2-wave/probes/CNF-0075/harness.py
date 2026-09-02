#!/usr/bin/env python3
"""Matched-pair fusion vs source benchmark harness for CNF-0075.

Workflows are deterministic capability pipelines. A case passes when every
required capability is produced by executed stages before the shared budget
is exhausted. Budget limit is applied by the harness, not requested of the
workflows.
"""
from __future__ import annotations

import copy
from typing import Any

BUDGET_LIMIT = 6
BUDGET_UNIT = "stage-cost"

SOURCE_RETRIEVE = "wf.source.retrieve"
SOURCE_TRANSFORM = "wf.source.transform"
FUSION = "wf.fusion.retrieve-then-transform"

CASES = (
    {
        "id": "case.lookup.a",
        "family": "lookup",
        "required_capabilities": ["parse", "lookup"],
    },
    {
        "id": "case.lookup.b",
        "family": "lookup",
        "required_capabilities": ["parse", "lookup"],
    },
    {
        "id": "case.rewrite.a",
        "family": "rewrite",
        "required_capabilities": ["parse", "rewrite"],
    },
    {
        "id": "case.rewrite.b",
        "family": "rewrite",
        "required_capabilities": ["parse", "rewrite"],
    },
    {
        "id": "case.combined.a",
        "family": "combined",
        "required_capabilities": ["parse", "lookup", "rewrite"],
    },
    {
        "id": "case.combined.b",
        "family": "combined",
        "required_capabilities": ["parse", "lookup", "rewrite"],
    },
)


def _stage(sid: str, capability: str | None, cost: int = 1, **extra: Any) -> dict:
    row = {"id": sid, "capability": capability, "cost": int(cost)}
    row.update(extra)
    return row


def source_retrieve() -> dict:
    return {
        "id": SOURCE_RETRIEVE,
        "role": "source",
        "title": "retrieve-only source",
        "stages": [
            _stage("parse", "parse"),
            _stage("lookup", "lookup"),
        ],
    }


def source_transform() -> dict:
    return {
        "id": SOURCE_TRANSFORM,
        "role": "source",
        "title": "transform-only source",
        "stages": [
            _stage("parse", "parse"),
            _stage("rewrite", "rewrite"),
        ],
    }


def fusion_union() -> dict:
    return {
        "id": FUSION,
        "role": "fusion",
        "title": "union fusion: parse + lookup + rewrite",
        "lineage": [SOURCE_RETRIEVE, SOURCE_TRANSFORM],
        "stages": [
            _stage("parse", "parse"),
            _stage("lookup", "lookup"),
            _stage("rewrite", "rewrite"),
        ],
    }


def fusion_stage_padded() -> dict:
    wf = fusion_union()
    wf["id"] = "wf.fusion.stage-padded"
    wf["title"] = "union fusion plus trailing no-op stages"
    wf["stages"] = list(wf["stages"]) + [
        _stage("noop.1", None),
        _stage("noop.2", None),
    ]
    return wf


def fusion_degraded() -> dict:
    return {
        "id": "wf.fusion.degraded-retrieve-only",
        "role": "fusion",
        "title": "fusion that dropped rewrite (lost source capability)",
        "lineage": [SOURCE_RETRIEVE, SOURCE_TRANSFORM],
        "stages": [
            _stage("parse", "parse"),
            _stage("lookup", "lookup"),
            _stage("noop.vanity", None),
        ],
    }


def fusion_per_case_regression() -> dict:
    wf = fusion_union()
    wf["id"] = "wf.fusion.lookup-regression"
    wf["title"] = "union fusion that fails case.lookup.b (aggregate still up)"
    wf["stages"] = [
        _stage("parse", "parse"),
        _stage("lookup", "lookup", fails_on=["case.lookup.b"]),
        _stage("rewrite", "rewrite"),
    ]
    return wf


def live_workflows() -> list[dict]:
    return [source_retrieve(), source_transform(), fusion_union()]


def case_ids() -> list[str]:
    return [c["id"] for c in CASES]


def stage_count(workflow: dict) -> int:
    return len(workflow.get("stages") or [])


def execute_case(
    workflow: dict, case: dict, budget_limit: int = BUDGET_LIMIT
) -> dict:
    remaining = float(budget_limit)
    collected: list[str] = []
    spent = 0.0
    executed = 0
    halted = "completed"
    for stage in workflow.get("stages") or []:
        cost = float(stage.get("cost") or 1)
        if cost > remaining:
            halted = "budget-exhausted"
            break
        remaining -= cost
        spent += cost
        executed += 1
        cap = stage.get("capability")
        fails_on = set(stage.get("fails_on") or [])
        if cap and case["id"] not in fails_on:
            collected.append(str(cap))
    required = list(case["required_capabilities"])
    passed = all(r in collected for r in required)
    return {
        "workflow_id": workflow["id"],
        "case_id": case["id"],
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "budget_limit": float(budget_limit),
        "budget_spent": spent,
        "stage_count": stage_count(workflow),
        "stages_executed": executed,
        "capabilities": collected,
        "required_capabilities": required,
        "halted": halted,
        "role": workflow.get("role"),
    }


def run_matrix(
    workflows: list[dict],
    cases: tuple[dict, ...] | list[dict] = CASES,
    budget_limit: int = BUDGET_LIMIT,
    budget_limits: dict[str, int] | None = None,
) -> dict:
    wfs = [copy.deepcopy(w) for w in workflows]
    cells: list[dict] = []
    by_wf: dict[str, dict[str, float]] = {}
    summaries: list[dict] = []
    for wf in wfs:
        limit = int((budget_limits or {}).get(wf["id"], budget_limit))
        scores: dict[str, float] = {}
        spent: list[float] = []
        for case in cases:
            cell = execute_case(wf, case, budget_limit=limit)
            cells.append(cell)
            scores[case["id"]] = cell["score"]
            spent.append(cell["budget_spent"])
        by_wf[wf["id"]] = scores
        n = max(len(scores), 1)
        summaries.append(
            {
                "id": wf["id"],
                "role": wf.get("role"),
                "title": wf.get("title"),
                "lineage": list(wf.get("lineage") or []),
                "stage_count": stage_count(wf),
                "budget_limit": float(limit),
                "budget_spent_mean": round(sum(spent) / n, 6),
                "pass_rate": round(sum(scores.values()) / n, 6),
                "stages": [s.get("id") for s in (wf.get("stages") or [])],
            }
        )
    limits = {s["budget_limit"] for s in summaries}
    return {
        "cases": [copy.deepcopy(c) for c in cases],
        "workflows": summaries,
        "cells": cells,
        "by_workflow": by_wf,
        "budget_parity": {
            "equal": len(limits) == 1,
            "budget_limit": float(budget_limit)
            if len(limits) == 1
            else sorted(limits),
            "unit": BUDGET_UNIT,
            "runs_compared": len(cells),
            "distinct_limits": sorted(limits),
        },
    }


def pass_rate(matrix: dict, workflow_id: str) -> float:
    for row in matrix["workflows"]:
        if row["id"] == workflow_id:
            return float(row["pass_rate"])
    raise KeyError(workflow_id)


def score_vector(matrix: dict, workflow_id: str, ids: list[str] | None = None) -> tuple:
    ids = ids or [c["id"] for c in matrix["cases"]]
    scores = matrix["by_workflow"][workflow_id]
    return tuple(scores[i] for i in ids)


def live_inventory(repo) -> dict:
    """Honest presence check for the catalog's claimed fusion inputs."""
    rels = [
        "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
        "10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md",
        "10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json",
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json",
        "command-center/confirmation/CNF-0074-workflow-replay-determinism.json",
        "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    ]
    present = []
    absent = []
    for rel in rels:
        path = repo / rel
        if path.is_file() and path.stat().st_size > 0:
            present.append(rel)
        else:
            absent.append(rel)
    certified = any("FUSION-AND-CERTIFICATION" in p for p in present)
    return {
        "certified_fusion_library_present": certified,
        "merge_maps_present": any("MERGE-AND-COMPOSITION-MAPS" in p for p in present),
        "checked": rels,
        "present": present,
        "absent": absent,
        "subject": (
            "No certified fused-workflow library is on this Linux worktree "
            "(merge maps and blueprint library are absent). CNF-0075 measures "
            "an executable matched-pair fusion reconstructed from two source "
            "workflows so the superiority gate is falsifiable here."
        ),
    }
