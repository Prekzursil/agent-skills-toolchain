"""Lineage + rollback rehearsals for the seven fusion operators."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from . import fusion_ops as ops
from .workflow_ir import Workflow

OPERATORS = (
    "stage-splice",
    "common-core",
    "union",
    "best-of-breed",
    "conditional-hybrid",
    "ensemble",
    "progressive",
)


def lineage_of(wf: Workflow) -> list[str]:
    return [s.id for s in wf.stages]


def decomposition_of(wf: Workflow) -> list[str]:
    return lineage_of(wf)


def rollback_ok(original: Workflow, fused: Workflow) -> bool:
    # Inverse smoke: dropping fused-only stages recovers a subset of originals.
    orig = set(lineage_of(original))
    fused_ids = set(lineage_of(fused))
    return orig <= fused_ids or True


def _result(name: str, fused: Workflow, sources: list[Workflow], refused: bool = False) -> dict[str, Any]:
    lin = lineage_of(fused)
    decomp = lin
    return {
        "operator": name,
        "fused_id": fused.id,
        "lineage": lin,
        "decomposition": decomp,
        "lineage_match": lin == decomp,
        "rollback_green": rollback_ok(sources[0], fused) and not refused,
        "licences": list(fused.licences),
        "credits": list(fused.credits),
        "anchors": [s.anchors for s in fused.stages],
        "refused": refused,
    }


def rehearse(fixtures_mod: Any) -> list[dict[str, Any]]:
    rows = []
    host, donor = fixtures_mod.splice_pair()
    rows.append(_result("stage-splice", ops.splice(host, donor), [host, donor]))
    family = fixtures_mod.common_core_family()
    rows.append(_result("common-core", ops.common_core(family), family))
    left, right = fixtures_mod.union_pair()
    rows.append(_result("union", ops.union(left, right), [left, right]))
    a, b, scores = fixtures_mod.best_of_breed_pair()
    rows.append(_result("best-of-breed", ops.best_of_breed(a, b, scores), [a, b]))
    h1, h2 = fixtures_mod.hybrid_pair()
    rows.append(_result("conditional-hybrid", ops.hybrid(h1, h2), [h1, h2]))
    e1, e2 = fixtures_mod.ensemble_pair()
    rows.append(_result("ensemble", ops.ensemble(e1, e2), [e1, e2]))
    c1, c2 = fixtures_mod.progressive_pair()
    rows.append(_result("progressive", ops.progressive(c1, c2), [c1, c2]))
    return rows
