#!/usr/bin/env python3
"""Minimal workflow IR helpers for stage-splice fusion.

This is not the full WFA-0044 IR (that artifact is absent on this tree). It is
the typed stage/contract subset the splice operator actually consumes:
named ports, exact types, canonical fingerprints, lineage.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

STRATEGY = "stage-splice"


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def ports(stage: dict[str, Any], which: str) -> list[dict[str, str]]:
    raw = stage.get(which) or []
    out: list[dict[str, str]] = []
    for p in raw:
        if not isinstance(p, dict):
            raise ValueError(f"port in {which} must be an object, got {type(p).__name__}")
        name = str(p.get("name") or "")
        typ = str(p.get("type") or "")
        if not name or not typ:
            raise ValueError(f"port in {which} requires name and type")
        out.append({"name": name, "type": typ})
    return out


def stage_fingerprint(stage: dict[str, Any]) -> str:
    """Structural fingerprint: kind + contracts + body + capability. Not the id.

    Id is a label. A renamed copy of the same stage must fingerprint equal so
    trivial forks cannot hide a no-op splice.
    """
    payload = {
        "body": stage.get("body"),
        "capability": stage.get("capability") or "pure-transform",
        "inputs": ports(stage, "inputs"),
        "kind": stage.get("kind"),
        "outputs": ports(stage, "outputs"),
        "performance": stage.get("performance"),
    }
    return canonical_sha256(payload)


def workflow_plan_fingerprint(workflow: dict[str, Any]) -> str:
    stages = workflow.get("stages") or []
    return canonical_sha256([stage_fingerprint(s) for s in stages])


def untouched_byte_identical(
    host: dict[str, Any], fusion: dict[str, Any], replaced_index: int
) -> list[dict[str, Any]]:
    host_stages = host.get("stages") or []
    fused_stages = fusion.get("stages") or []
    rows = []
    for i, src in enumerate(host_stages):
        if i == replaced_index:
            continue
        dst = fused_stages[i] if i < len(fused_stages) else None
        src_b = canonical_bytes(src)
        dst_b = canonical_bytes(dst) if dst is not None else b""
        rows.append(
            {
                "index": i,
                "host_stage_id": src.get("id"),
                "identical": src_b == dst_b,
                "host_sha256": hashlib.sha256(src_b).hexdigest(),
                "fusion_sha256": hashlib.sha256(dst_b).hexdigest() if dst is not None else "",
            }
        )
    return rows


def deepcopy_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(workflow)
