#!/usr/bin/env python3
"""Base typed workflow plus the 20-rename / 20-gate mutant families."""
from __future__ import annotations

import copy
from typing import Any, Callable

BASE: dict[str, Any] = {
    "id": "wf.council.critique-then-act",
    "title": "Critique then act",
    "stages": [
        {
            "id": "ingest",
            "kind": "intake",
            "roles": ["scribe"],
            "tools": [{"id": "t_read", "class": "read"}],
            "gate": {"op": "ALL", "args": [{"atom": "input_present"}]},
        },
        {
            "id": "plan",
            "kind": "deliberate",
            "roles": ["architect", "critic"],
            "tools": [{"id": "t_search", "class": "search"}],
            "gate": {
                "op": "ANY",
                "args": [
                    {"atom": "unanimity"},
                    {"atom": "timeout", "params": {"seconds": 30}},
                ],
            },
        },
        {
            "id": "refute",
            "kind": "adversarial",
            "roles": ["refuter"],
            "tools": [{"id": "t_grep", "class": "search"}],
            "gate": {"op": "NOT", "arg": {"atom": "overclaim"}},
        },
        {
            "id": "act",
            "kind": "execute",
            "roles": ["implementer"],
            "tools": [
                {"id": "t_write", "class": "write"},
                {"id": "t_shell", "class": "shell"},
            ],
            "gate": {
                "op": "ALL",
                "args": [
                    {"atom": "stage_done", "stage": "plan"},
                    {"atom": "stage_done", "stage": "refute"},
                    {"atom": "coverage", "params": {"min": 0.8}},
                ],
            },
        },
        {
            "id": "verify",
            "kind": "measure",
            "roles": ["auditor"],
            "tools": [{"id": "t_test", "class": "test"}],
            "gate": {"op": "ALL", "args": [{"atom": "probe_green"}]},
        },
    ],
    "edges": [
        {"from": "ingest", "to": "plan", "gate": {"atom": "ok"}},
        {"from": "plan", "to": "refute", "gate": {"atom": "plan_ready"}},
        {"from": "plan", "to": "act", "gate": {"atom": "skip_refute"}},
        {"from": "refute", "to": "act", "gate": {"atom": "refute_done"}},
        {"from": "act", "to": "verify", "gate": {"op": "ALL", "args": [{"atom": "wrote"}]}},
    ],
}


def _rewrite_pred(pred: Any, mapping: dict[str, str]) -> Any:
    if not isinstance(pred, dict):
        return pred
    out = copy.deepcopy(pred)
    if "stage" in out and out["stage"] in mapping:
        out["stage"] = mapping[out["stage"]]
    if "arg" in out:
        out["arg"] = _rewrite_pred(out["arg"], mapping)
    if "args" in out and isinstance(out["args"], list):
        out["args"] = [_rewrite_pred(a, mapping) for a in out["args"]]
    return out


def rename_workflow(wf: dict, tag: str) -> dict:
    """Rename every identifier. Vocabulary (kinds, role types, tool classes,
    predicate atoms) is preserved — those are the mechanism, not names."""
    src = copy.deepcopy(wf)
    mapping = {s["id"]: f"{tag}__{s['id']}" for s in src["stages"]}
    src["id"] = f"{tag}::{src.get('id')}"
    src["title"] = f"{tag} {src.get('title')}"
    for s in src["stages"]:
        s["id"] = mapping[s["id"]]
        s["title"] = f"{tag}:{s.get('kind')}"
        for t in s.get("tools") or []:
            if isinstance(t, dict) and "id" in t:
                t["id"] = f"{tag}__{t['id']}"
        if "gate" in s:
            s["gate"] = _rewrite_pred(s["gate"], mapping)
    for e in src["edges"]:
        e["from"] = mapping[e["from"]]
        e["to"] = mapping[e["to"]]
        if "gate" in e:
            e["gate"] = _rewrite_pred(e["gate"], mapping)
        e["id"] = f"{tag}__{e['from']}__{e['to']}"
    return src


RENAME_TAGS = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "omicron",
    "pi",
    "rho",
    "sigma",
    "tau",
    "upsilon",
]


def rename_mutants(wf: dict | None = None) -> list[tuple[str, dict]]:
    base = wf or BASE
    return [(tag, rename_workflow(base, tag)) for tag in RENAME_TAGS]


def _patch_atom(pred: Any, old: str, new: str) -> Any:
    if not isinstance(pred, dict):
        return pred
    out = copy.deepcopy(pred)
    if out.get("atom") == old:
        out["atom"] = new
    if "arg" in out:
        out["arg"] = _patch_atom(out["arg"], old, new)
    if "args" in out and isinstance(out["args"], list):
        out["args"] = [_patch_atom(a, old, new) for a in out["args"]]
    return out


def _set_param(pred: Any, atom: str, key: str, value: Any) -> Any:
    if not isinstance(pred, dict):
        return pred
    out = copy.deepcopy(pred)
    if out.get("atom") == atom:
        params = dict(out.get("params") or {})
        params[key] = value
        out["params"] = params
    if "arg" in out:
        out["arg"] = _set_param(out["arg"], atom, key, value)
    if "args" in out and isinstance(out["args"], list):
        out["args"] = [_set_param(a, atom, key, value) for a in out["args"]]
    return out


GatePatch = Callable[[dict], None]


def _gate_patches() -> list[tuple[str, GatePatch]]:
    def stage(name: str) -> Callable[[dict], dict]:
        def find(wf: dict) -> dict:
            for s in wf["stages"]:
                if s["id"] == name:
                    return s
            raise KeyError(name)

        return find

    def edge(frm: str, to: str) -> Callable[[dict], dict]:
        def find(wf: dict) -> dict:
            for e in wf["edges"]:
                if e["from"] == frm and e["to"] == to:
                    return e
            raise KeyError((frm, to))

        return find

    patches: list[tuple[str, GatePatch]] = []

    def add(name: str, fn: GatePatch) -> None:
        patches.append((name, fn))

    add("ingest_all_to_any", lambda wf: stage("ingest")(wf).__setitem__("gate", {"op": "ANY", "args": [{"atom": "input_present"}]}))
    add("plan_any_to_all", lambda wf: stage("plan")(wf).__setitem__("gate", {"op": "ALL", "args": [{"atom": "unanimity"}, {"atom": "timeout", "params": {"seconds": 30}}]}))
    add("plan_drop_timeout", lambda wf: stage("plan")(wf).__setitem__("gate", {"op": "ANY", "args": [{"atom": "unanimity"}]}))
    add("plan_timeout_31", lambda wf: stage("plan")(wf).__setitem__("gate", _set_param(stage("plan")(wf)["gate"], "timeout", "seconds", 31)))
    add("refute_atom_underclaim", lambda wf: stage("refute")(wf).__setitem__("gate", _patch_atom(stage("refute")(wf)["gate"], "overclaim", "underclaim")))
    add("refute_drop_not", lambda wf: stage("refute")(wf).__setitem__("gate", {"atom": "overclaim"}))
    add("act_coverage_0_9", lambda wf: stage("act")(wf).__setitem__("gate", _set_param(stage("act")(wf)["gate"], "coverage", "min", 0.9)))
    add("act_drop_plan_done", lambda wf: stage("act")(wf).__setitem__("gate", {"op": "ALL", "args": [{"atom": "stage_done", "stage": "refute"}, {"atom": "coverage", "params": {"min": 0.8}}]}))
    add("act_all_to_any", lambda wf: stage("act")(wf).__setitem__("gate", {**stage("act")(wf)["gate"], "op": "ANY"}))
    add("verify_atom_red", lambda wf: stage("verify")(wf).__setitem__("gate", _patch_atom(stage("verify")(wf)["gate"], "probe_green", "probe_red")))
    add("verify_add_conjunct", lambda wf: stage("verify")(wf).__setitem__("gate", {"op": "ALL", "args": [{"atom": "probe_green"}, {"atom": "size_floor"}]}))
    add("edge_ok_to_ready", lambda wf: edge("ingest", "plan")(wf).__setitem__("gate", {"atom": "ready"}))
    add("edge_plan_ready_to_planned", lambda wf: edge("plan", "refute")(wf).__setitem__("gate", {"atom": "planned"}))
    add("edge_skip_refute_to_bypass", lambda wf: edge("plan", "act")(wf).__setitem__("gate", {"atom": "bypass"}))
    add("edge_refute_done_to_cleared", lambda wf: edge("refute", "act")(wf).__setitem__("gate", {"atom": "cleared"}))
    add("edge_wrote_to_committed", lambda wf: edge("act", "verify")(wf).__setitem__("gate", _patch_atom(edge("act", "verify")(wf)["gate"], "wrote", "committed")))
    add("edge_wrote_all_to_any", lambda wf: edge("act", "verify")(wf).__setitem__("gate", {"op": "ANY", "args": [{"atom": "wrote"}]}))
    add("ingest_add_schema_ok", lambda wf: stage("ingest")(wf).__setitem__("gate", {"op": "ALL", "args": [{"atom": "input_present"}, {"atom": "schema_ok"}]}))
    add("plan_unanimity_to_majority", lambda wf: stage("plan")(wf).__setitem__("gate", _patch_atom(stage("plan")(wf)["gate"], "unanimity", "majority")))
    add("act_coverage_max", lambda wf: stage("act")(wf).__setitem__("gate", _set_param(stage("act")(wf)["gate"], "coverage", "max", 1.0)))
    return patches


def gate_mutants(wf: dict | None = None) -> list[tuple[str, dict]]:
    base = wf or BASE
    out: list[tuple[str, dict]] = []
    for name, patch in _gate_patches():
        mutant = copy.deepcopy(base)
        patch(mutant)
        out.append((name, mutant))
    if len(out) != 20:
        raise RuntimeError(f"expected 20 gate mutants, got {len(out)}")
    return out
