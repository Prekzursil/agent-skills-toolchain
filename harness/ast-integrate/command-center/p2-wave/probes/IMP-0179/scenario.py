#!/usr/bin/env python3
"""Deterministic fused/generated workflow catalog for IMP-0179 probes."""
from __future__ import annotations

from typing import Any

from lineage import GENERATED_STRATEGY, attach_lineage, strip_lineage

COMPONENTS: dict[str, dict[str, str]] = {
    "cmp.ingest.http": {
        "component_id": "cmp.ingest.http",
        "version": "1.4.2",
        "licence": "Apache-2.0",
        "role": "stage",
        "span": "foundry/components/ingest.http@1.4.2",
    },
    "cmp.gate.schema": {
        "component_id": "cmp.gate.schema",
        "version": "0.9.1",
        "licence": "MIT",
        "role": "gate",
        "span": "foundry/components/gate.schema@0.9.1",
    },
    "cmp.render.markdown": {
        "component_id": "cmp.render.markdown",
        "version": "2.0.0",
        "licence": "BSD-3-Clause",
        "role": "stage",
        "span": "foundry/components/render.markdown@2.0.0",
    },
    "cmp.spec.prompt-one": {
        "component_id": "cmp.spec.prompt-one",
        "version": "2026.08.06",
        "licence": "LicenseRef-Prompt-One-Corpus",
        "role": "spec",
        "span": "_USER-PROMPTS.md:11152-11170",
    },
    "cmp.generator.foundry": {
        "component_id": "cmp.generator.foundry",
        "version": "0.3.0",
        "licence": "Apache-2.0",
        "role": "generator",
        "span": "foundry/generator@0.3.0",
    },
    "cmp.review.adversary": {
        "component_id": "cmp.review.adversary",
        "version": "1.1.0",
        "licence": "MPL-2.0",
        "role": "stage",
        "span": "foundry/components/review.adversary@1.1.0",
    },
}


def _stage(component_id: str, stage_id: str) -> dict[str, Any]:
    src = COMPONENTS[component_id]
    return {
        "id": stage_id,
        "component_id": component_id,
        "version": src["version"],
        "licence": src["licence"],
    }


def generated_review_pack() -> dict[str, Any]:
    return attach_lineage(
        {
            "workflow_id": "wf.generated.review-pack",
            "kind": "generated",
            "stages": [
                _stage("cmp.spec.prompt-one", "s0-spec"),
                _stage("cmp.review.adversary", "s1-review"),
            ],
        },
        sources=[COMPONENTS["cmp.spec.prompt-one"], COMPONENTS["cmp.generator.foundry"]],
        fusion_strategy=GENERATED_STRATEGY,
        kind="generated",
    )


def generated_ingest_gate() -> dict[str, Any]:
    return attach_lineage(
        {
            "workflow_id": "wf.generated.ingest-gate",
            "kind": "generated",
            "stages": [
                _stage("cmp.ingest.http", "s0-ingest"),
                _stage("cmp.gate.schema", "s1-gate"),
            ],
        },
        sources=[
            COMPONENTS["cmp.ingest.http"],
            COMPONENTS["cmp.gate.schema"],
            COMPONENTS["cmp.generator.foundry"],
        ],
        fusion_strategy=GENERATED_STRATEGY,
        kind="generated",
    )


def fused_union_alpha() -> dict[str, Any]:
    a = generated_ingest_gate()
    b = generated_review_pack()
    return attach_lineage(
        {
            "workflow_id": "wf.fused.union.alpha",
            "kind": "fused",
            "stages": list(a["stages"]) + list(b["stages"]),
        },
        sources=[
            {
                "component_id": a["workflow_id"],
                "version": "1.0.0",
                "licence": "Apache-2.0",
                "role": "host",
                "span": "wf.generated.ingest-gate lineage",
            },
            {
                "component_id": b["workflow_id"],
                "version": "1.0.0",
                "licence": "MPL-2.0",
                "role": "donor",
                "span": "wf.generated.review-pack lineage",
            },
        ],
        fusion_strategy="union",
        kind="fused",
    )


def fused_splice_beta() -> dict[str, Any]:
    host = fused_union_alpha()
    return attach_lineage(
        {
            "workflow_id": "wf.fused.splice.beta",
            "kind": "fused",
            "stages": host["stages"][:-1] + [_stage("cmp.render.markdown", "s-render")],
        },
        sources=[
            {
                "component_id": host["workflow_id"],
                "version": "1.0.0",
                "licence": "MPL-2.0",
                "role": "host",
                "span": "wf.fused.union.alpha lineage",
            },
            COMPONENTS["cmp.render.markdown"],
        ],
        fusion_strategy="stage-splice",
        kind="fused",
    )


def fused_ensemble_gamma() -> dict[str, Any]:
    return attach_lineage(
        {
            "workflow_id": "wf.fused.ensemble.gamma",
            "kind": "fused",
            "stages": [
                _stage("cmp.ingest.http", "s0-ingest"),
                _stage("cmp.review.adversary", "s1-review"),
                _stage("cmp.render.markdown", "s2-render"),
            ],
        },
        sources=[
            COMPONENTS["cmp.ingest.http"],
            COMPONENTS["cmp.review.adversary"],
            COMPONENTS["cmp.render.markdown"],
        ],
        fusion_strategy="ensemble",
        kind="fused",
    )


def catalog() -> list[dict[str, Any]]:
    return [
        generated_ingest_gate(),
        generated_review_pack(),
        fused_union_alpha(),
        fused_splice_beta(),
        fused_ensemble_gamma(),
    ]


def stripped_union_fixture() -> dict[str, Any]:
    return strip_lineage(fused_union_alpha())
