"""Union fusion with duplicate-stage collapse.

Structurally identical stages (same mechanism fingerprint) collapse to one
representative. Capabilities on collapsed copies are unioned so coverage is a
superset of both parents. Topology is remapped onto the collapsed ids.

naive_concat is the named broken sibling: it concatenates stages and is the
falsifier of idempotence (union(w, w) == w by fingerprint).
"""
from __future__ import annotations

import copy
from typing import Any

from fingerprint import stage_fingerprint


def _new_id(fp: str) -> str:
    return f"stage-{fp[:12]}"


def union_fuse(left: dict, right: dict) -> dict:
    """Set-union of stages by mechanism fingerprint, then topology by fp-pairs."""
    seen: dict[str, dict] = {}
    order: list[str] = []
    for workflow in (left, right):
        for stage in workflow.get("stages") or []:
            fp = stage_fingerprint(stage)
            if fp not in seen:
                kept = copy.deepcopy(stage)
                kept["id"] = _new_id(fp)
                caps = sorted(set(kept.get("capabilities") or []))
                kept["capabilities"] = caps
                seen[fp] = kept
                order.append(fp)
            else:
                extra = set(stage.get("capabilities") or [])
                seen[fp]["capabilities"] = sorted(set(seen[fp].get("capabilities") or []) | extra)

    edge_order: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()
    for workflow in (left, right):
        local = {s["id"]: stage_fingerprint(s) for s in workflow.get("stages") or []}
        for edge in workflow.get("edges") or []:
            src_fp = local[edge["from"]]
            dst_fp = local[edge["to"]]
            pair = (src_fp, dst_fp)
            if pair in seen_edges:
                continue
            seen_edges.add(pair)
            edge_order.append({"from": seen[src_fp]["id"], "to": seen[dst_fp]["id"]})

    return {
        "id": f"union({left.get('id')},{right.get('id')})",
        "fusion": {
            "strategy": "union-duplicate-stage-collapse",
            "sources": [left.get("id"), right.get("id")],
        },
        "stages": [seen[fp] for fp in order],
        "edges": edge_order,
    }


def naive_concat(left: dict, right: dict) -> dict:
    """Broken concatenating union. Kept as the idempotence falsifier."""
    stages: list[dict] = []
    edges: list[dict] = []
    for prefix, workflow in (("L", left), ("R", right)):
        remap: dict[str, str] = {}
        for stage in workflow.get("stages") or []:
            new_id = f"{prefix}-{stage['id']}"
            remap[stage["id"]] = new_id
            kept = copy.deepcopy(stage)
            kept["id"] = new_id
            stages.append(kept)
        for edge in workflow.get("edges") or []:
            edges.append({"from": remap[edge["from"]], "to": remap[edge["to"]]})
    return {
        "id": f"concat({left.get('id')},{right.get('id')})",
        "fusion": {"strategy": "naive-concat", "sources": [left.get("id"), right.get("id")]},
        "stages": stages,
        "edges": edges,
    }


def drop_stage(workflow: dict, stage_id: str) -> dict:
    """Planted lossy fusion: remove one stage and dangling edges."""
    out = copy.deepcopy(workflow)
    out["stages"] = [s for s in out.get("stages") or [] if s.get("id") != stage_id]
    out["edges"] = [
        e
        for e in out.get("edges") or []
        if e.get("from") != stage_id and e.get("to") != stage_id
    ]
    out["id"] = f"lossy({workflow.get('id')},drop={stage_id})"
    return out


def rename_workflow(workflow: dict, suffix: str = "_renamed") -> dict:
    """Rename every stage id. Mechanism fingerprint must be invariant."""
    out = copy.deepcopy(workflow)
    remap = {s["id"]: f"{s['id']}{suffix}" for s in out.get("stages") or []}
    for stage in out["stages"]:
        stage["id"] = remap[stage["id"]]
    for edge in out.get("edges") or []:
        edge["from"] = remap[edge["from"]]
        edge["to"] = remap[edge["to"]]
    out["id"] = f"{workflow.get('id')}{suffix}"
    return out


def mutate_one_gate(workflow: dict) -> dict:
    """Change one gate atom. Mechanism fingerprint must change."""
    out = copy.deepcopy(workflow)
    stages = out.get("stages") or []
    if not stages:
        raise ValueError("no stages")
    gates: Any = stages[0].setdefault("gates", {})
    if isinstance(gates, dict) and "all" in gates and gates["all"]:
        atom = gates["all"][0]
        if isinstance(atom, dict) and "atom" in atom:
            atom["atom"] = f"{atom['atom']}#mutated"
        else:
            gates["all"][0] = {"atom": "mutated-gate"}
    else:
        stages[0]["gates"] = {"all": [{"atom": "mutated-gate"}]}
    out["id"] = f"{workflow.get('id')}#gate-mutant"
    return out
