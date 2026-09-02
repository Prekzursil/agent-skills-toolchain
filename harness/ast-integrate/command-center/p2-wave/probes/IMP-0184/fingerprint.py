"""Rename-invariant structural mechanism fingerprint for a workflow.

Fingerprint payload (IMP-0170 vocabulary): stage kinds, role set, gate
predicates, tool classes, topology. Stage and workflow identifiers are
stripped. Multiplicity is kept so concatenating a workflow with itself cannot
hash-equal the original — the cheapest falsifier of naive union-by-concat.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _canon(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canon(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        items = [_canon(x) for x in value]
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":")))
    if isinstance(value, tuple):
        return _canon(list(value))
    if isinstance(value, set):
        return _canon(sorted(value, key=lambda x: json.dumps(x, sort_keys=True, separators=(",", ":"))))
    return value


def dumps(value: Any) -> str:
    return json.dumps(_canon(value), sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


def stage_mechanism(stage: dict) -> dict:
    """Typed mechanism of one stage, identifiers omitted."""
    return {
        "kind": stage.get("kind"),
        "roles": list(stage.get("roles") or []),
        "gates": stage.get("gates") if stage.get("gates") is not None else {},
        "tools": list(stage.get("tools") or []),
        "inputs": list(stage.get("inputs") or []),
        "outputs": list(stage.get("outputs") or []),
    }


def stage_fingerprint(stage: dict) -> str:
    return digest(stage_mechanism(stage))


def _id_map(workflow: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for stage in workflow.get("stages") or []:
        sid = stage.get("id")
        if not isinstance(sid, str) or not sid:
            raise ValueError("stage missing id")
        out[sid] = stage_fingerprint(stage)
    return out


def workflow_fingerprint(workflow: dict) -> str:
    """Multiplicity-aware fingerprint over stages + topology.

    Stage fingerprints are collected as a sorted *list* (duplicates kept).
    Edges are pairs of those fingerprints, also with multiplicity. Dropping
    topology from this payload would make a gate-preserving rewire invisible;
    that mutation is the IMP-0170 detector and is asserted by probe 1.
    """
    id_to_fp = _id_map(workflow)
    stage_fps = sorted(id_to_fp.values())
    edges: list[list[str]] = []
    for edge in workflow.get("edges") or []:
        src = edge.get("from")
        dst = edge.get("to")
        if src not in id_to_fp or dst not in id_to_fp:
            raise ValueError(f"edge {edge!r} names an unknown stage")
        edges.append([id_to_fp[src], id_to_fp[dst]])
    edges.sort()
    return digest({"edges": edges, "stages": stage_fps})


def workflow_fingerprint_without_topology(workflow: dict) -> str:
    """Broken sibling used only as a detector control. Not an API for fusion."""
    id_to_fp = _id_map(workflow)
    return digest({"stages": sorted(id_to_fp.values())})


def internally_unique_stages(workflow: dict) -> bool:
    fps = [stage_fingerprint(s) for s in workflow.get("stages") or []]
    return len(fps) == len(set(fps))
