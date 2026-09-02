#!/usr/bin/env python3
"""Scaled analogue registries for the ARC-0010 A2 generator.

Live libraries 09-WORKFLOW-BLUEPRINT-LIBRARY.json and
12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent. A2 has no protocol
kind, so protocols are extra `doc` entries. That mapping is disclosed.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ARC-0010"))
import generator as G  # noqa: E402

SHARED_FIXED = 7  # plugin, marketplace, hook, rule, overview doc, two catalogs

HALF = {"workflows": 48, "protocols": 24, "presets": 32}
TARGET = {"workflows": 96, "protocols": 48, "presets": 64}


def live_skill_md_count(repo: Path) -> int:
    n = 0
    for p in repo.rglob("SKILL.md"):
        parts = p.relative_to(repo).as_posix().split("/")
        if "p2-wave" in parts or "node_modules" in parts:
            continue
        n += 1
    return n


def analogue_skill_count() -> int:
    reg = G.load_default_registry()
    return sum(1 for e in reg["entries"] if e["kind"] == "skill")


def expected_file_count(n_wf: int, n_proto: int, n_preset: int, n_skill: int) -> int:
    return SHARED_FIXED + n_skill + n_proto + n_wf + n_preset


def _kinds(registry: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for e in registry["entries"]:
        out.setdefault(e["kind"], []).append(e)
    return out


def _clone(kinds: dict[str, list[dict[str, Any]]], kind: str, new_id: str, **updates: Any) -> dict[str, Any]:
    row = copy.deepcopy(kinds[kind][0])
    row["id"] = new_id
    row.update(updates)
    return row


def build_registry(n_wf: int, n_proto: int, n_preset: int, n_skill: int) -> dict[str, Any]:
    if min(n_wf, n_preset, n_skill) < 1:
        raise ValueError("need at least 1 workflow, 1 preset, 1 skill")
    base = G.load_default_registry()
    kinds = _kinds(base)
    skills = [_clone(kinds, "skill", f"skill.s{i:03d}", name=f"s{i:03d}") for i in range(n_skill)]
    skills[0] = copy.deepcopy(kinds["skill"][0])
    wfs = [_clone(kinds, "workflow_blueprint", f"wf.n{i:03d}") for i in range(n_wf)]
    presets = [_clone(kinds, "council_preset", f"council.preset.n{i:03d}") for i in range(n_preset)]
    protos = [
        _clone(
            kinds,
            "doc",
            f"protocol.n{i:03d}",
            title=f"Protocol analogue {i:03d}",
            body=(
                "A2 has no protocol kind; this doc is the file-write analogue "
                f"for protocol {i:03d}."
            ),
        )
        for i in range(n_proto)
    ]
    plugin = copy.deepcopy(kinds["plugin_manifest"][0])
    plugin["skill_ids"] = [s["id"] for s in skills]
    wfcat = copy.deepcopy(kinds["workflow_catalog"][0])
    wfcat["member_ids"] = [w["id"] for w in wfs]
    ccat = copy.deepcopy(kinds["council_catalog"][0])
    ccat["member_ids"] = [p["id"] for p in presets]
    out = copy.deepcopy(base)
    out["entries"] = (
        [plugin, copy.deepcopy(kinds["marketplace_entry"][0])]
        + skills
        + [
            copy.deepcopy(kinds["hook"][0]),
            copy.deepcopy(kinds["rule"][0]),
            copy.deepcopy(kinds["doc"][0]),
        ]
        + protos
        + wfs
        + presets
        + [wfcat, ccat]
    )
    return out


def mutate_workflow_on_error(registry: dict[str, Any]) -> str:
    for e in registry["entries"]:
        if e["kind"] == "workflow_blueprint":
            cur = e["stopping"]["on_error"]
            e["stopping"]["on_error"] = "skip" if cur == "halt" else "halt"
            return str(e["id"])
    raise RuntimeError("no workflow_blueprint")


def mutate_preset_quorum(registry: dict[str, Any]) -> str:
    for e in registry["entries"]:
        if e["kind"] == "council_preset":
            q = int(e["voting"]["quorum"])
            e["voting"]["quorum"] = 3 if q >= 4 else 4
            return str(e["id"])
    raise RuntimeError("no council_preset")


def dirty_ids_for(registry: dict[str, Any], changed_id: str) -> set[str]:
    dirty = {changed_id}
    for e in registry["entries"]:
        kind = e["kind"]
        if kind in {"workflow_catalog", "council_catalog"} and changed_id in e["member_ids"]:
            dirty.add(e["id"])
        if kind == "plugin_manifest":
            refs = list(e["skill_ids"]) + list(e["hook_ids"]) + list(e["rule_ids"])
            if changed_id in refs:
                dirty.add(e["id"])
        if kind == "marketplace_entry" and e["plugin_id"] == changed_id:
            dirty.add(e["id"])
    return dirty
