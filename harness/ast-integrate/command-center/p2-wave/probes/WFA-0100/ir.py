#!/usr/bin/env python3
"""Typed workflow IR subset consumed by WFA-0100 stage-splice INSERT.

WFA-0044 (full IR spec) is absent on this worktree. This module is the typed
stage/port/anchor subset the insert operator actually needs: named ports,
scalar input_type/output_type, canonical fingerprints, source_anchor, and a
validator that rejects execution entrypoints.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

OPERATOR = "stage-splice"
RUNTIME_KEYS = frozenset({"execute", "entrypoint", "runtime", "__main__"})


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def deepcopy_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(workflow)


def _scalar_ports(type_name: str | None, default_name: str) -> list[dict[str, str]]:
    if not type_name:
        return []
    return [{"name": default_name, "type": str(type_name)}]


def ports(node: dict[str, Any], which: str) -> list[dict[str, str]]:
    """Named ports, or a single scalar input_type/output_type as a port."""
    raw = node.get(which)
    if isinstance(raw, list) and raw:
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
    if which in {"inputs", "entry"}:
        return _scalar_ports(node.get("input_type") or node.get("entry_type"), "in")
    if which in {"outputs", "exit"}:
        return _scalar_ports(node.get("output_type") or node.get("exit_type"), "out")
    return []


def stage_scalar_in(stage: dict[str, Any]) -> str | None:
    if stage.get("input_type"):
        return str(stage["input_type"])
    ins = ports(stage, "inputs")
    if len(ins) == 1:
        return ins[0]["type"]
    return None


def stage_scalar_out(stage: dict[str, Any]) -> str | None:
    if stage.get("output_type"):
        return str(stage["output_type"])
    outs = ports(stage, "outputs")
    if len(outs) == 1:
        return outs[0]["type"]
    return None


def stage_fingerprint(stage: dict[str, Any]) -> str:
    """Structural fingerprint: kind + contracts + body. Id is a label."""
    payload = {
        "body": stage.get("body"),
        "capability": stage.get("capability") or "pure-transform",
        "input_type": stage_scalar_in(stage),
        "inputs": ports(stage, "inputs"),
        "kind": stage.get("kind"),
        "output_type": stage_scalar_out(stage),
        "outputs": ports(stage, "outputs"),
    }
    return canonical_sha256(payload)


def untouched_host_stages(
    host: dict[str, Any], fusion: dict[str, Any], insert_index: int
) -> list[dict[str, Any]]:
    """Every original host stage must appear byte-identical (index may shift)."""
    host_stages = host.get("stages") or []
    fused_stages = fusion.get("stages") or []
    rows: list[dict[str, Any]] = []
    for i, src in enumerate(host_stages):
        fused_i = i if i < insert_index else i + 1
        dst = fused_stages[fused_i] if 0 <= fused_i < len(fused_stages) else None
        src_b = canonical_bytes(src)
        dst_b = canonical_bytes(dst) if dst is not None else b""
        rows.append(
            {
                "host_index": i,
                "fused_index": fused_i,
                "host_stage_id": src.get("id"),
                "identical": src_b == dst_b,
                "host_sha256": hashlib.sha256(src_b).hexdigest(),
                "fusion_sha256": hashlib.sha256(dst_b).hexdigest() if dst is not None else "",
            }
        )
    return rows


def validate_ir(doc: Any) -> dict[str, Any]:
    """WorkflowIR subset: stages, typed ports, source_anchor, no runtime."""
    errors: list[str] = []
    if not isinstance(doc, dict):
        return {"ok": False, "errors": ["ir-not-object"]}
    if not doc.get("id"):
        errors.append("missing-id")
    runtime_hit = sorted(k for k in RUNTIME_KEYS if k in doc)
    if runtime_hit:
        errors.append(f"runtime-keys:{','.join(runtime_hit)}")
    if not doc.get("source_anchor"):
        errors.append("workflow-missing-source_anchor")
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        errors.append("stages-missing")
        return {"ok": False, "errors": errors}
    ids: list[str] = []
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict):
            errors.append(f"stage[{i}]-not-object")
            continue
        sid = str(stage.get("id") or "")
        if not sid:
            errors.append(f"stage[{i}]-missing-id")
        else:
            ids.append(sid)
        if not stage.get("source_anchor"):
            errors.append(f"stage[{sid or i}]-missing-source_anchor")
        rt = sorted(k for k in RUNTIME_KEYS if k in stage)
        if rt:
            errors.append(f"stage[{sid or i}]-runtime-keys:{','.join(rt)}")
        try:
            ins = ports(stage, "inputs")
            outs = ports(stage, "outputs")
        except ValueError as exc:
            errors.append(f"stage[{sid or i}]-ports:{exc}")
            continue
        if not ins and not stage_scalar_in(stage):
            errors.append(f"stage[{sid or i}]-missing-input-type")
        if not outs and not stage_scalar_out(stage):
            errors.append(f"stage[{sid or i}]-missing-output-type")
    if len(ids) != len(set(ids)):
        errors.append("duplicate-stage-ids")
    return {"ok": not errors, "errors": errors, "stage_ids": ids, "stage_count": len(stages)}
