#!/usr/bin/env python3
"""Minimal vendor-neutral workflow IR used by the WFA-0054 round-trip harness.

This is not a second execution runtime. Every node that is an IR record must
carry a source_anchor; a node without one is schema-invalid.
"""
from __future__ import annotations

from typing import Any

IR_VERSION = "wfa-ir-1"

ROOT_REQUIRED = (
    "ir_version",
    "id",
    "adapter_id",
    "source_anchor",
    "stages",
    "roles",
    "gates",
    "barriers",
    "loops",
    "checkpoints",
    "fan_out",
    "stopping",
    "resume",
    "lineage",
    "tool_policy",
)

NODE_LISTS = (
    "stages",
    "roles",
    "gates",
    "barriers",
    "loops",
    "checkpoints",
    "fan_out",
)

RECORD_KEYS = ("stopping", "resume", "lineage", "tool_policy")


class IrError(ValueError):
    pass


def node(payload: dict[str, Any], source_anchor: str) -> dict[str, Any]:
    out = dict(payload)
    out["source_anchor"] = source_anchor
    return out


def empty_ir(
    *,
    adapter_id: str,
    native_id: str,
    source_anchor: str,
) -> dict[str, Any]:
    return {
        "ir_version": IR_VERSION,
        "id": native_id,
        "adapter_id": adapter_id,
        "source_anchor": source_anchor,
        "stages": [],
        "roles": [],
        "gates": [],
        "barriers": [],
        "loops": [],
        "checkpoints": [],
        "fan_out": [],
        "stopping": node({"expression": None}, f"{source_anchor}#stopping"),
        "resume": node({"enabled": False}, f"{source_anchor}#resume"),
        "lineage": node({"parent_ids": []}, f"{source_anchor}#lineage"),
        "tool_policy": node({"allow": [], "deny": []}, f"{source_anchor}#tool_policy"),
    }


def validate_ir(ir: Any) -> None:
    if not isinstance(ir, dict):
        raise IrError("IR is not an object")
    for key in ROOT_REQUIRED:
        if key not in ir:
            raise IrError(f"missing required IR field {key}")
    if ir.get("ir_version") != IR_VERSION:
        raise IrError(f"unsupported ir_version {ir.get('ir_version')!r}")
    if not str(ir.get("source_anchor") or "").strip():
        raise IrError("root source_anchor empty")
    for key in NODE_LISTS:
        items = ir.get(key)
        if not isinstance(items, list):
            raise IrError(f"{key} must be a list")
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise IrError(f"{key}[{i}] is not an object")
            if not str(item.get("source_anchor") or "").strip():
                raise IrError(f"{key}[{i}] missing source_anchor")
    for key in RECORD_KEYS:
        rec = ir.get(key)
        if not isinstance(rec, dict):
            raise IrError(f"{key} must be an object")
        if not str(rec.get("source_anchor") or "").strip():
            raise IrError(f"{key} missing source_anchor")
