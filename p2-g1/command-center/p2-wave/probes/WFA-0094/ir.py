"""Workflow IR subset for WFA-0094: five semantic dimensions, not a runtime.

WFA-0044 (vendor-neutral IR spec) and WFA-0054 (round-trip fidelity) artifacts
are absent on this tree. This module is the differ's *consumption* shape for
the five dimensions the catalog names: stage, role, gate, tool, stop-rule.

It is not a substitute for WFA-0044. Nodes that cannot be expressed here are
recorded as residual unknowns on the unit artifact, not silently dropped.
Every comparable node must carry a source_anchor.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

DIMENSIONS: tuple[str, ...] = ("stage", "role", "gate", "tool", "stop-rule")

COLLECTION: dict[str, str] = {
    "stage": "stages",
    "role": "roles",
    "gate": "gates",
    "tool": "tools",
    "stop-rule": "stop_rules",
}

# Provenance / listing order — not capability. Dropped from payload compare.
META_KEYS = frozenset({"source_anchor", "seq", "order", "index", "pos"})

# List fields compared as sets (order-insensitive nested members).
SET_FIELDS = frozenset(
    {
        "capabilities",
        "allows",
        "denies",
        "depends_on",
        "roles",
        "tools",
        "inputs",
        "outputs",
        "tags",
    }
)


class IRError(ValueError):
    """Malformed IR: missing id or source_anchor, or duplicate ids."""


def _require_anchor(node: dict[str, Any], where: str) -> None:
    if not isinstance(node, dict):
        raise IRError(f"{where}: node is not an object")
    nid = node.get("id")
    if not isinstance(nid, str) or not nid.strip():
        raise IRError(f"{where}: missing id")
    anchor = node.get("source_anchor")
    if not isinstance(anchor, str) or not anchor.strip():
        raise IRError(f"{where} id={nid!r}: missing source_anchor")


def validate_ir(ir: dict[str, Any]) -> None:
    if not isinstance(ir, dict):
        raise IRError("IR is not an object")
    _require_anchor(ir, "workflow")
    for dim, key in COLLECTION.items():
        seen: set[str] = set()
        for i, node in enumerate(ir.get(key) or []):
            loc = f"{key}[{i}]"
            _require_anchor(node, loc)
            nid = node["id"]
            if nid in seen:
                raise IRError(f"{loc}: duplicate id {nid!r} in dimension {dim}")
            seen.add(nid)


def _norm_value(key: str, value: Any) -> Any:
    if key in SET_FIELDS and isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict):
                items.append(_norm_obj(item))
            else:
                items.append(item)
        try:
            return sorted(items, key=lambda x: repr(x))
        except TypeError:
            return items
    if isinstance(value, dict):
        return _norm_obj(value)
    if isinstance(value, list):
        return [_norm_value(key, v) for v in value]
    return value


def _norm_obj(obj: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in sorted(obj):
        if k in META_KEYS:
            continue
        out[k] = _norm_value(k, obj[k])
    return out


def semantic_payload(node: dict[str, Any]) -> dict[str, Any]:
    """Capability payload: id kept for readability; provenance/order stripped."""
    return _norm_obj(deepcopy(node))


def index_dimension(ir: dict[str, Any], dim: str) -> dict[str, dict[str, Any]]:
    if dim not in COLLECTION:
        raise IRError(f"unknown dimension {dim!r}")
    validate_ir(ir)
    out: dict[str, dict[str, Any]] = {}
    for node in ir.get(COLLECTION[dim]) or []:
        out[node["id"]] = semantic_payload(node)
    return out


def shuffled(ir: dict[str, Any]) -> dict[str, Any]:
    """Reverse every dimension list. Semantic identity must be unchanged."""
    clone = deepcopy(ir)
    for key in COLLECTION.values():
        items = list(clone.get(key) or [])
        items.reverse()
        clone[key] = items
    return clone


def iter_corpus(irs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = list(irs)
    for ir in out:
        validate_ir(ir)
    return out
