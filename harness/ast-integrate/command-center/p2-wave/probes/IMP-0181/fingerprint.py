#!/usr/bin/env python3
"""Rename-invariant structural mechanism fingerprint for a workflow candidate.

IMP-0170 contract (consumed here, not assumed delivered): the fingerprint covers
stage kinds, role set, gate predicates, tool classes, and topology. Renaming
every identifier leaves it unchanged; changing one gate predicate changes it.

Identifiers (workflow id/name, stage id/name) are substituted with $ID inside
gate predicates. Typed vocabulary (kinds, role names, tool classes, predicate
operators) is NOT substituted: those are the mechanism, not labels.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
WL_ROUNDS = 6


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def collect_identifiers(workflow: dict) -> set[str]:
    ids: set[str] = set()
    for key in ("id", "name"):
        val = workflow.get(key)
        if isinstance(val, str) and val:
            ids.add(val)
    for stage in workflow.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        for key in ("id", "name"):
            val = stage.get(key)
            if isinstance(val, str) and val:
                ids.add(val)
    return ids


def normalize_predicate(pred: str, identifiers: set[str]) -> str:
    if not isinstance(pred, str):
        pred = json.dumps(pred, sort_keys=True, default=str)

    def repl(match: re.Match[str]) -> str:
        tok = match.group(0)
        return "$ID" if tok in identifiers else tok

    return IDENT_RE.sub(repl, pred)


def _stage_next(stage: dict) -> list[str]:
    nxt = stage.get("next")
    if nxt is None:
        nxt = stage.get("successors")
    return [str(x) for x in _as_list(nxt)]


def _local_signature(stage: dict, identifiers: set[str]) -> tuple:
    kind = str(stage.get("kind") or stage.get("type") or "")
    roles = tuple(sorted(str(r) for r in _as_list(stage.get("roles"))))
    gates = tuple(
        sorted(
            normalize_predicate(str(g), identifiers)
            for g in _as_list(stage.get("gates") or stage.get("gate_predicates"))
        )
    )
    tools = tuple(sorted(str(t) for t in _as_list(stage.get("tools") or stage.get("tool_classes"))))
    return (kind, roles, gates, tools)


def structural_record(workflow: dict) -> dict:
    """Canonical typed record used as the fingerprint preimage."""
    identifiers = collect_identifiers(workflow)
    stages = [s for s in (workflow.get("stages") or []) if isinstance(s, dict)]
    by_id = {str(s.get("id")): s for s in stages}
    localsig = {str(s.get("id")): _local_signature(s, identifiers) for s in stages}
    successors = {str(s.get("id")): _stage_next(s) for s in stages}
    predecessors: dict[str, list[str]] = {sid: [] for sid in by_id}
    for src, dests in successors.items():
        for dest in dests:
            if dest in predecessors:
                predecessors[dest].append(src)

    colors = dict(localsig)
    for _ in range(WL_ROUNDS):
        nxt: dict[str, tuple] = {}
        for sid in by_id:
            succ = tuple(sorted(colors.get(d, ("missing",)) for d in successors[sid]))
            pred = tuple(sorted(colors.get(p, ("missing",)) for p in predecessors[sid]))
            nxt[sid] = (colors[sid], succ, pred)
        colors = nxt

    ordered = sorted(by_id.keys(), key=lambda sid: (colors[sid], sid))
    index = {sid: i for i, sid in enumerate(ordered)}
    canon_stages = []
    for sid in ordered:
        kind, roles, gates, tools = localsig[sid]
        canon_stages.append(
            {
                "kind": kind,
                "roles": list(roles),
                "gates": list(gates),
                "tools": list(tools),
            }
        )
    edges = sorted(
        (index[src], index[dest])
        for src, dests in successors.items()
        for dest in dests
        if dest in index
    )
    return {"stages": canon_stages, "edges": [list(e) for e in edges]}


def fingerprint(workflow: dict) -> str:
    rec = structural_record(workflow)
    blob = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def rename_workflow(workflow: dict, mapping: dict[str, str]) -> dict:
    """Rename identifiers; mapping keys are old ids/names."""
    cloned = copy.deepcopy(workflow)

    def mapped(value: Any) -> Any:
        if isinstance(value, str):
            return mapping.get(value, value)
        if isinstance(value, list):
            return [mapped(v) for v in value]
        return value

    for key in ("id", "name"):
        if key in cloned:
            cloned[key] = mapped(cloned[key])
    for stage in cloned.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        for key in ("id", "name", "next", "successors"):
            if key in stage:
                stage[key] = mapped(stage[key])
        if "gates" in stage:
            stage["gates"] = [
                _rewrite_pred(g, mapping) if isinstance(g, str) else g
                for g in _as_list(stage["gates"])
            ]
        if "gate_predicates" in stage:
            stage["gate_predicates"] = [
                _rewrite_pred(g, mapping) if isinstance(g, str) else g
                for g in _as_list(stage["gate_predicates"])
            ]
    return cloned


def _rewrite_pred(pred: str, mapping: dict[str, str]) -> str:
    # Longest keys first so "review-council" wins over "review".
    items = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)

    def repl(match: re.Match[str]) -> str:
        tok = match.group(0)
        return mapping.get(tok, tok)

    out = IDENT_RE.sub(repl, pred)
    for old, new in items:
        if old and old in out:
            out = out.replace(old, new)
    return out


def mutate_one_gate(workflow: dict, new_pred: str = "mutated_gate_predicate == 1") -> dict:
    cloned = copy.deepcopy(workflow)
    stages = [s for s in (cloned.get("stages") or []) if isinstance(s, dict)]
    if not stages:
        raise ValueError("workflow has no stages to mutate")
    target = stages[0]
    gates = _as_list(target.get("gates") or target.get("gate_predicates"))
    if gates:
        gates[0] = new_pred
    else:
        gates = [new_pred]
    target["gates"] = gates
    return cloned


def drop_topology(workflow: dict) -> dict:
    """Ablation used as a detector-failure control: fingerprint without edges."""
    rec = structural_record(workflow)
    rec["edges"] = []
    blob = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return rec, hashlib.sha256(blob).hexdigest()
