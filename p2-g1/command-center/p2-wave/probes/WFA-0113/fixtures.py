#!/usr/bin/env python3
"""Fixture corpus and workflows for WFA-0113.

WFA-0112 (benchmark case corpus) and fusion-operator artifacts are absent on
this worktree. The harness consumes this fixture corpus so the matched-pair
contract is executable and falsifiable here. Paths that would be loaded when
present are recorded by emit_artifact.inventory().
"""
from __future__ import annotations

from typing import Any

SEED = 20260824
BUDGET_LIMIT = 6.0
BUDGET_UNIT = "stage-cost"

SOURCE_RETRIEVE = "wf.source.retrieve"
SOURCE_TRANSFORM = "wf.source.transform"
FUSION_UNION = "wf.fusion.union"
FUSION_CRASH = "wf.fusion.crash"
FUSION_HUNGRY = "wf.fusion.hungry"
NEAR_A = "wf.near.twin-a"
NEAR_B = "wf.near.twin-b"

UPSTREAM_CORPUS = "command-center/wfa/WFA-0112-benchmark-case-corpus.json"
UPSTREAM_FUSION = [
    "command-center/wfa/WFA-0103-fusion-best-of-breed.json",
    "command-center/wfa/WFA-0111-fusion-operator-selection-policy.json",
    "10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
]


def _stage(
    sid: str,
    capability: str | None,
    cost: float = 1.0,
    action: str = "emit",
    **extra: Any,
) -> dict:
    row = {
        "id": sid,
        "capability": capability,
        "cost": float(cost),
        "action": action,
    }
    row.update(extra)
    return row


def cases() -> list[dict]:
    return [
        {
            "id": "case.lookup.a",
            "family": "lookup",
            "payload": {"query": "alpha", "mode": "lookup"},
            "required_capabilities": ["parse", "lookup"],
            "oracle": {"kind": "capability-subset"},
        },
        {
            "id": "case.lookup.b",
            "family": "lookup",
            "payload": {"query": "beta", "mode": "lookup"},
            "required_capabilities": ["parse", "lookup"],
            "oracle": {"kind": "capability-subset"},
        },
        {
            "id": "case.rewrite.a",
            "family": "rewrite",
            "payload": {"query": "gamma", "mode": "rewrite"},
            "required_capabilities": ["parse", "rewrite"],
            "oracle": {"kind": "capability-subset"},
        },
        {
            "id": "case.combined.a",
            "family": "combined",
            "payload": {"query": "delta", "mode": "combined"},
            "required_capabilities": ["parse", "lookup", "rewrite"],
            "oracle": {"kind": "capability-subset"},
        },
    ]


def source_retrieve() -> dict:
    return {
        "id": SOURCE_RETRIEVE,
        "role": "source",
        "title": "retrieve-only source",
        "requested_budget": 99.0,
        "quality": 0.50,
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
        "requested_budget": 99.0,
        "quality": 0.50,
        "stages": [
            _stage("parse", "parse"),
            _stage("rewrite", "rewrite"),
        ],
    }


def fusion_union() -> dict:
    return {
        "id": FUSION_UNION,
        "role": "fusion",
        "title": "union fusion: parse + lookup + rewrite",
        "lineage": [SOURCE_RETRIEVE, SOURCE_TRANSFORM],
        "requested_budget": 99.0,
        "quality": 0.90,
        "stages": [
            _stage("parse", "parse"),
            _stage("lookup", "lookup"),
            _stage("rewrite", "rewrite"),
        ],
    }


def fusion_crash() -> dict:
    return {
        "id": FUSION_CRASH,
        "role": "fusion",
        "title": "planted crashing fused candidate (failed-arm fixture)",
        "lineage": [SOURCE_RETRIEVE, SOURCE_TRANSFORM],
        "requested_budget": 99.0,
        "quality": 0.0,
        "stages": [
            _stage("boom", None, action="crash"),
        ],
    }


def fusion_hungry() -> dict:
    return {
        "id": FUSION_HUNGRY,
        "role": "fusion",
        "title": "over-budget fused candidate (harness must halt)",
        "lineage": [SOURCE_RETRIEVE, SOURCE_TRANSFORM],
        "requested_budget": 99.0,
        "quality": 0.10,
        "stages": [_stage(f"step.{i}", "parse" if i == 0 else None) for i in range(8)],
    }


def near_twin_a() -> dict:
    return {
        "id": NEAR_A,
        "role": "source",
        "title": "near-twin A (quality 0.50)",
        "requested_budget": 99.0,
        "quality": 0.50,
        "stages": [_stage("parse", "parse"), _stage("lookup", "lookup")],
    }


def near_twin_b() -> dict:
    return {
        "id": NEAR_B,
        "role": "source",
        "title": "near-twin B (quality 0.51; below planted floor of 0.05)",
        "requested_budget": 99.0,
        "quality": 0.51,
        "stages": [_stage("parse", "parse"), _stage("lookup", "lookup")],
    }


def comparison_workflows() -> list[dict]:
    return [
        source_retrieve(),
        source_transform(),
        fusion_union(),
        fusion_crash(),
        fusion_hungry(),
        near_twin_a(),
        near_twin_b(),
    ]


def control_workflows() -> list[dict]:
    return [source_retrieve(), fusion_union()]
