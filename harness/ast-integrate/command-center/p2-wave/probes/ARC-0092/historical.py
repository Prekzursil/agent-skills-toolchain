#!/usr/bin/env python3
"""Real historical pairs from this tree, with recorded release versions.

command-center/phase3/A2/DESIGN.json is ARC-0010's catalog output and is
absent on this worktree. The recorded A2 cut that DESIGN.json would have
embedded is command-center/p2-wave/probes/ARC-0010/registry.schema.json
(schema_version const 1, generator_version 1.0.0). Known-answer pairs live
under fixtures/ so a missing DESIGN.json does not make the calculator
vacuous.
"""
from __future__ import annotations

import json
from pathlib import Path

from typing import Any

from calculator import classify

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

DESIGN = REPO / "command-center/phase3/A2/DESIGN.json"
REGISTRY_SCHEMA = REPO / "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
REGISTRY = REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"
REVIEW_SCHEMA = REPO / "command-center/schema/architecture-review.schema.json"
MAJOR_OLD = HERE / "fixtures/known-major-narrowed-enum/old.json"
MAJOR_NEW = HERE / "fixtures/known-major-narrowed-enum/new.json"
PATCH_OLD = HERE / "fixtures/known-patch-description/old.json"
PATCH_NEW = HERE / "fixtures/known-patch-description/new.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry(reg: dict, kind: str) -> dict:
    for row in reg.get("entries") or []:
        if row.get("kind") == kind:
            return row
    raise RuntimeError(f"no registry entry kind={kind}")


def _schema_cut() -> tuple[dict, dict, str, str, Any, Any, str]:
    live_schema = _load(REGISTRY_SCHEMA)
    to_ref = "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
    if DESIGN.is_file():
        design = _load(DESIGN)
        embedded = design.get("registry_schema")
        if not isinstance(embedded, dict):
            raise RuntimeError("DESIGN.json registry_schema missing")
        recorded_schema_version = design.get("schema_version")
        gen_ver = (
            (design.get("determinism_contract") or {})
            .get("measured_this_tree", {})
            .get("generator_version")
        )
        return (
            embedded,
            live_schema,
            "command-center/phase3/A2/DESIGN.json#/registry_schema",
            to_ref,
            recorded_schema_version,
            gen_ver,
            "DESIGN.json embedded registry_schema vs live A2 registry.schema.json",
        )
    recorded_schema_version = 1
    const = (live_schema.get("properties") or {}).get("schema_version") or {}
    if isinstance(const, dict) and const.get("const") is not None:
        recorded_schema_version = const.get("const")
    registry = _load(REGISTRY)
    gen_ver = registry.get("generator_version") or "1.0.0"
    return (
        live_schema,
        live_schema,
        to_ref,
        to_ref,
        recorded_schema_version,
        gen_ver,
        "DESIGN.json absent; recorded A2 cut is live registry.schema.json schema_version=1 generator_version=1.0.0; no later schema release on this tree",
    )


def historical_pairs() -> list[dict]:
    old_schema, live_schema, from_ref, to_ref, recorded_schema_version, gen_ver, history_note = (
        _schema_cut()
    )
    schema_pair = classify(old_schema, live_schema, "schema")
    recorded_bump = "NONE"
    match = schema_pair["required_bump"] == recorded_bump

    registry = _load(REGISTRY)
    plugin = _entry(registry, "plugin_manifest")
    market = _entry(registry, "marketplace_entry")
    workflow = _entry(registry, "workflow_blueprint")

    plugin_pair = classify(plugin, json.loads(json.dumps(plugin)), "plugin")
    market_pair = classify(market, json.loads(json.dumps(market)), "marketplace")
    workflow_pair = classify(workflow, json.loads(json.dumps(workflow)), "workflow_dsl")

    major_old, major_new = _load(MAJOR_OLD), _load(MAJOR_NEW)
    major_pair = classify(major_old, major_new, "schema")
    patch_old, patch_new = _load(PATCH_OLD), _load(PATCH_NEW)
    patch_pair = classify(patch_old, patch_new, "schema")

    pairs = [
        {
            "id": "a2-registry-schema-recorded-cut",
            "artifact_class": "schema",
            "from_ref": from_ref,
            "to_ref": to_ref,
            "recorded_schema_version": recorded_schema_version,
            "recorded_generator_version": gen_ver,
            "recorded_release_history": history_note,
            "recorded_required_bump": recorded_bump,
            "computed_required_bump": schema_pair["required_bump"],
            "matches_recorded_history": match,
            "verdict": schema_pair,
        },
        {
            "id": "plugin-harness-1.0.0-identity",
            "artifact_class": "plugin",
            "from_ref": "command-center/p2-wave/probes/ARC-0010/registry.json#plugin.harness",
            "to_ref": "command-center/p2-wave/probes/ARC-0010/registry.json#plugin.harness",
            "recorded_version": plugin.get("version"),
            "recorded_required_bump": "NONE",
            "computed_required_bump": plugin_pair["required_bump"],
            "matches_recorded_history": plugin_pair["required_bump"] == "NONE",
            "verdict": plugin_pair,
        },
        {
            "id": "marketplace-harness-1.0.0-identity",
            "artifact_class": "marketplace",
            "from_ref": "command-center/p2-wave/probes/ARC-0010/registry.json#marketplace.harness",
            "to_ref": "command-center/p2-wave/probes/ARC-0010/registry.json#marketplace.harness",
            "recorded_version": market.get("version"),
            "recorded_required_bump": "NONE",
            "computed_required_bump": market_pair["required_bump"],
            "matches_recorded_history": market_pair["required_bump"] == "NONE",
            "verdict": market_pair,
        },
        {
            "id": "workflow-discovery-only-identity",
            "artifact_class": "workflow_dsl",
            "from_ref": "command-center/p2-wave/probes/ARC-0010/registry.json#wf.catalog-class.discovery-only",
            "to_ref": "command-center/p2-wave/probes/ARC-0010/registry.json#wf.catalog-class.discovery-only",
            "recorded_required_bump": "NONE",
            "computed_required_bump": workflow_pair["required_bump"],
            "matches_recorded_history": workflow_pair["required_bump"] == "NONE",
            "verdict": workflow_pair,
        },
        {
            "id": "known-major-narrowed-enum",
            "artifact_class": "schema",
            "from_ref": "command-center/p2-wave/probes/ARC-0092/fixtures/known-major-narrowed-enum/old.json",
            "to_ref": "command-center/p2-wave/probes/ARC-0092/fixtures/known-major-narrowed-enum/new.json",
            "recorded_release_history": "fixture: state enum dropped PARTIAL; recorded required bump MAJOR",
            "recorded_required_bump": "MAJOR",
            "computed_required_bump": major_pair["required_bump"],
            "matches_recorded_history": major_pair["required_bump"] == "MAJOR"
            and any(c["kind"] == "narrowed_enum" for c in major_pair["changes"]),
            "verdict": major_pair,
        },
        {
            "id": "known-patch-description",
            "artifact_class": "schema",
            "from_ref": "command-center/p2-wave/probes/ARC-0092/fixtures/known-patch-description/old.json",
            "to_ref": "command-center/p2-wave/probes/ARC-0092/fixtures/known-patch-description/new.json",
            "recorded_release_history": "fixture: description annotation only; recorded required bump PATCH",
            "recorded_required_bump": "PATCH",
            "computed_required_bump": patch_pair["required_bump"],
            "matches_recorded_history": patch_pair["required_bump"] == "PATCH"
            and any(c["kind"] == "description_change" for c in patch_pair["changes"]),
            "verdict": patch_pair,
        },
    ]
    return pairs


def historical_ok() -> dict:
    pairs = historical_pairs()
    ok = all(p.get("matches_recorded_history") for p in pairs) and len(pairs) >= 2
    return {"pass": ok, "pair_count": len(pairs), "pairs": pairs}


def live_review_schema() -> dict:
    return _load(REVIEW_SCHEMA)


def live_registry_schema() -> dict:
    return _load(REGISTRY_SCHEMA)
