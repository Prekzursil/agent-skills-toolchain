"""Capability-loss detector for fusions (IMP-0191)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FAILURE_CLASS = "capability-loss"
FAILURE_CLASS_ID = "fusion.capability-loss"


def load_library(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def index_workflows(library: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in library.get("workflows") or []:
        out[str(row["id"])] = row
    return out


def _tokens(stage: dict[str, Any]) -> set[str]:
    toks: set[str] = set()
    for cap in stage.get("capabilities") or []:
        toks.add(str(cap))
    for gate in stage.get("gates") or []:
        toks.add("gate:" + str(gate))
    for tool in stage.get("tools") or []:
        toks.add("tool:" + str(tool))
    for rule in stage.get("stop_rules") or []:
        toks.add("stop:" + str(rule))
    for rec in stage.get("recovery") or []:
        toks.add("recovery:" + str(rec))
    return toks


def capability_vector(workflow: dict[str, Any]) -> list[str]:
    toks: set[str] = set()
    for stage in workflow.get("stages") or []:
        toks |= _tokens(stage)
    return sorted(toks)


def resolve_sources(fusion: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [catalog[str(sid)] for sid in fusion.get("sources") or [] if str(sid) in catalog]


def lost_capabilities(fusion: dict[str, Any], sources: list[dict[str, Any]]) -> list[str]:
    union: set[str] = set()
    for src in sources:
        union |= set(capability_vector(src))
    lost = union - set(capability_vector(fusion))
    return sorted(lost)


def detect_capability_loss(fusion: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    lost = lost_capabilities(fusion, sources)
    fired = bool(lost)
    return {
        "fired": fired,
        "lost": lost,
        "set_difference_empty": not fired,
        "failure_class": FAILURE_CLASS if fired else None,
        "failure_class_id": FAILURE_CLASS_ID if fired else None,
        "fusion_vector": capability_vector(fusion),
        "source_union": sorted({t for s in sources for t in capability_vector(s)}),
    }


def evaluate_admitted(library: dict[str, Any]) -> dict[str, Any]:
    catalog = index_workflows(library)
    admitted = library.get("admitted_fusion_ids") or [
        wid for wid, wf in catalog.items() if wf.get("kind") == "fusion" and wf.get("admitted")
    ]
    results = []
    empty_all = True
    for fid in admitted:
        fusion = catalog[str(fid)]
        sources = resolve_sources(fusion, catalog)
        det = detect_capability_loss(fusion, sources)
        rec = {
            "fusion_id": fid,
            "fired": det["fired"],
            "lost": det["lost"],
            "fusion_vector": det["fusion_vector"],
            "source_union": det["source_union"],
        }
        results.append(rec)
        if det["fired"]:
            empty_all = False
    return {
        "admitted_count": len(results),
        "set_difference_empty_for_all": empty_all,
        "results": results,
    }


def plant_dropped_stage(fusion: dict[str, Any], stage_id: str) -> dict[str, Any]:
    planted = json.loads(json.dumps(fusion))
    planted["stages"] = [s for s in planted.get("stages") or [] if str(s.get("id")) != stage_id]
    planted.pop("capability_vector", None)
    return planted
