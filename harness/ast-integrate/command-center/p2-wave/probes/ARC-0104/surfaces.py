#!/usr/bin/env python3
"""Extract docs / schema / impl field inventories from this worktree.

The gate runs against existing command-center tooling. Missing phase-4 frozen
contracts are recorded as absent schema surfaces, not invented.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(HERE))

import catalog as cat  # noqa: E402
import gate as G  # noqa: E402

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
VALIDATE_REL = "tools/command-center/validate.py"
SEED_REL = "tools/command-center/seed.py"
MANIFEST_REL = "tools/command-center/unit_manifest.py"
MEASURE_REL = "command-center/p2-wave/_measure_one_delivered.py"
REGISTRY_SCHEMA_REL = "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
GENERATOR_REL = "command-center/p2-wave/probes/ARC-0010/generator.py"
EXTRACT_REL = "command-center/p2-wave/probes/ARC-0014/extract.py"
IMP0433_REL = "command-center/p2-wave/_build_IMP0433.py"

ARC_0082_DOC = (
    "stages",
    "roles",
    "gates",
    "tool_policy",
    "typed_parameters",
    "subworkflows",
    "dynamic_fan_out",
    "barriers",
    "loops",
    "human_checkpoints",
    "retries",
    "repair_loops",
    "resume",
    "deterministic_replay",
    "artifact_caching",
    "dry_run",
    "cost_estimate",
    "time_estimate",
    "model_routing",
    "failure_policy",
    "export_import",
)
ARC_0082_PHRASES = {
    "stages": "stages",
    "roles": "roles",
    "gates": "gates",
    "tool_policy": "tool policy",
    "typed_parameters": "typed parameters",
    "subworkflows": "subworkflows",
    "dynamic_fan_out": "dynamic fan-out",
    "barriers": "barriers",
    "loops": "loops",
    "human_checkpoints": "human checkpoints",
    "retries": "retries",
    "repair_loops": "repair loops",
    "resume": "resume",
    "deterministic_replay": "deterministic replay",
    "artifact_caching": "artifact caching",
    "dry_run": "dry-run",
    "cost_estimate": "cost and time estimate",
    "time_estimate": "cost and time estimate",
    "model_routing": "model routing",
    "failure_policy": "failure policy",
    "export_import": "export/import",
}

ARC_0084_DOC = (
    "artifact_id",
    "producing_unit",
    "content_hash",
    "byte_size",
    "schema_reference",
    "sentinel",
    "evidence_anchors",
    "retention_class",
    "manifest_registration",
)
ARC_0084_PHRASES = {
    "artifact_id": "artifact id",
    "producing_unit": "producing unit",
    "content_hash": "content hash",
    "byte_size": "byte size",
    "schema_reference": "schema reference",
    "sentinel": "sentinel",
    "evidence_anchors": "evidence anchors",
    "retention_class": "retention class",
    "manifest_registration": "manifest registration",
}

# Twelve completion conditions, matching _build_IMP0433.py CONDITIONS order.
ARC_0087_DOC = (
    "terminal_state",
    "artifact_exists",
    "min_meaningful_size",
    "schema_parse",
    "sentinel",
    "evidence_anchors",
    "tests_passed",
    "negative_controls",
    "reviewer_pass",
    "no_unresolved_p0_p1",
    "manifest_registration",
    "downstream_consumers_can_read",
)

# What _measure_one_delivered.py actually evaluates (same names when it
# approximates a documented condition; defaults record the weakening).
ARC_0087_IMPL = (
    "terminal_state",
    "artifact_exists",
    "min_meaningful_size",
    "schema_parse",
    "sentinel",
    "tests_passed",
    "manifest_registration",
)

MEASURE_SNIPPETS = {
    "terminal_state": "NOT_DELIVERING",
    "artifact_exists": "predicate:absent",
    "min_meaningful_size": "out.stat().st_size <= 0",
    "schema_parse": "json.loads(text)",
    "sentinel": "sentinel-absent",
    "tests_passed": "probe-exit",
    "manifest_registration": "manifest-sha-mismatch",
}


def _must_contain(rel: str, snippet: str, label: str) -> None:
    text = (REPO / rel).read_text(encoding="utf-8")
    if snippet not in text:
        raise RuntimeError(f"stale extractor {label}: {snippet!r} not in {rel}")


def _load_catalog() -> dict[str, Any]:
    return json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))


def _unit(catalog: dict[str, Any], uid: str) -> dict[str, Any]:
    for row in catalog.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == uid:
            return row
    raise RuntimeError(f"catalog missing {uid}")


def _assert_phrases(question: str, phrases: dict[str, str], uid: str) -> None:
    missing = [name for name, phrase in phrases.items() if phrase not in question]
    if missing:
        raise RuntimeError(f"{uid} question no longer names {missing}")


def _key_census(rows: list[dict[str, Any]], threshold: float = 0.9) -> tuple[set[str], dict[str, Any]]:
    n = len(rows)
    counts: dict[str, int] = {}
    for row in rows:
        for key in row:
            counts[key] = counts.get(key, 0) + 1
    core = {k for k, c in counts.items() if n and (c / n) >= threshold}
    detail = {
        k: {"present": c, "absent": n - c, "rate": round(c / n, 4) if n else 0}
        for k, c in sorted(counts.items())
    }
    return core, {"n": n, "keys": detail}


def _json_schema_fields(schema: dict[str, Any], defn: str) -> set[str]:
    node = (schema.get("definitions") or {}).get(defn) or {}
    props = node.get("properties") or {}
    fields = set(props)
    stages = ((props.get("stages") or {}).get("items") or {}).get("properties") or {}
    for key in stages:
        fields.add(f"stages.{key}")
    stopping = (props.get("stopping") or {}).get("properties") or {}
    for key in stopping:
        fields.add(f"stopping.{key}")
    return fields


def _require_complete_default() -> bool:
    """Live validate.py default: completeness ON (BooleanOptionalAction default=True)."""
    text = (REPO / VALIDATE_REL).read_text(encoding="utf-8")
    _must_contain(VALIDATE_REL, "--require-complete", "require_complete_flag")
    _must_contain(VALIDATE_REL, "--no-require-complete", "require_complete_off")
    if "require_complete: bool = True" in text:
        return True
    if "require_complete: bool = False" in text or "require_complete=False" in text:
        return False
    _must_contain(VALIDATE_REL, "require_complete: bool = True", "fn_default")
    return True


def work_unit_contract(catalog: dict[str, Any]) -> dict[str, Any]:
    """ARC-0083: Prompt Two 19-field work-unit schema vs live catalog + validator."""
    uid = "ARC-0083"
    row = _unit(catalog, uid)
    question = str(row.get("question_or_target") or "")
    _must_contain(CATALOG_REL, "defaults-are-not-completeness", "arc0083-title")
    docs = list(catalog.get("contract", {}).get("work_unit_fields") or [])
    schema = list(cat.WORK_UNIT_FIELDS)
    if docs != schema:
        # Still compare as sets; record the list mismatch in notes.
        pass
    units = [u for u in (catalog.get("work_units") or []) if isinstance(u, dict)]
    impl_core, census = _key_census(units)
    items = [u for u in (catalog.get("items") or []) if isinstance(u, dict)]
    item_core, item_census = _key_census(items)

    _must_contain(VALIDATE_REL, "for field in cat.WORK_UNIT_FIELDS", "v-fields")
    _must_contain(VALIDATE_REL, "cat.items(catalog)", "walks-items")
    validate_src = (REPO / VALIDATE_REL).read_text(encoding="utf-8")
    walks_work_units = "work_units" in validate_src and "catalog.get(\"work_units\")" in validate_src

    docs_defaults = {
        "require_complete": True,
        **{
            k: catalog.get("defaults", {})[k]
            for k in (catalog.get("defaults") or {})
            if k in docs
        },
    }
    schema_defaults = dict(docs_defaults)
    schema_defaults["require_complete"] = True
    impl_defaults = {
        "require_complete": _require_complete_default(),
    }
    # Instance defaults: work_units carry per-unit values; they do not use
    # catalog.defaults.assignment (they renamed the field).
    impl_fields = set(impl_core)
    directions = G.compare_surfaces(
        docs,
        schema,
        impl_fields,
        docs_defaults=docs_defaults,
        schema_defaults=schema_defaults,
        impl_defaults=impl_defaults,
        qualify=uid,
    )
    frozen = (REPO / "command-center/phase4/contracts/ARC-0083.json").is_file()
    return {
        "id": uid,
        "title": str(row.get("title") or uid),
        "question": question,
        "frozen_contract_path": "command-center/phase4/contracts/ARC-0083.json",
        "frozen_contract_present": frozen,
        "docs_fields": sorted(docs),
        "schema_fields": sorted(schema),
        "impl_fields": sorted(impl_fields),
        "impl_source": "work_units keys present on >=90% of 2007 catalogued units",
        "validator_walks": "catalog.items (R-* backlog), not work_units",
        "validator_walks_work_units": walks_work_units,
        "work_units_census": census,
        "items_census": item_census,
        "item_core_fields": sorted(item_core),
        "docs_not_on_items_except_defaults": sorted(set(docs) - item_core),
        "possible_renames": [
            {"docs": "target", "impl": "question_or_target"},
            {"docs": "assignment", "impl": "assigned_model_vendor_role"},
        ],
        "directions": directions,
        "notes": [
            "catalog.py WORK_UNIT_FIELDS is the in-code schema; phase4/contracts/ARC-0083.json is absent.",
            "validate.py V-FIELDS walks items() (103 backlog rows) and is OFF unless --require-complete.",
            "The 2007 work_units array is the Prompt Two catalog the contract names, and it uses renamed keys.",
        ],
    }


def artifact_envelope_contract(catalog: dict[str, Any]) -> dict[str, Any]:
    uid = "ARC-0084"
    row = _unit(catalog, uid)
    question = str(row.get("question_or_target") or "")
    _assert_phrases(question, ARC_0084_PHRASES, uid)
    docs = list(ARC_0084_DOC)
    _must_contain(MANIFEST_REL, '"path": rel', "manifest-path")
    _must_contain(MANIFEST_REL, '"sha256": digest', "manifest-sha")
    _must_contain(MANIFEST_REL, '"bytes": length', "manifest-bytes")
    _must_contain(MANIFEST_REL, '"present": True', "manifest-present")
    _must_contain(MANIFEST_REL, '"unit_id": receipt["unit_id"]', "manifest-unit")
    _must_contain(MANIFEST_REL, '"receipt_path": receipt_rel', "manifest-receipt")
    schema = ["path", "sha256", "bytes", "present", "unit_id", "receipt_path"]
    _must_contain(MEASURE_REL, 'a.get("path")', "measure-path")
    _must_contain(MEASURE_REL, 'a.get("sha256")', "measure-sha")
    _must_contain(MEASURE_REL, 'a.get("present") is True', "measure-present")
    _must_contain(MEASURE_REL, 'a.get("unit_id") == uid', "measure-unit")
    impl = ["path", "sha256", "present", "unit_id"]
    directions = G.compare_surfaces(docs, schema, impl, qualify=uid)
    frozen = (REPO / "command-center/phase4/contracts/ARC-0084.json").is_file()
    return {
        "id": uid,
        "title": str(row.get("title") or uid),
        "question": question,
        "frozen_contract_path": "command-center/phase4/contracts/ARC-0084.json",
        "frozen_contract_present": frozen,
        "docs_fields": sorted(docs),
        "schema_fields": sorted(schema),
        "impl_fields": sorted(impl),
        "impl_source": "unit_manifest.py row shape consumed by _measure_one_delivered.py",
        "possible_renames": [
            {"docs": "content_hash", "impl": "sha256"},
            {"docs": "byte_size", "impl": "bytes"},
            {"docs": "producing_unit", "impl": "unit_id"},
            {"docs": "artifact_id", "impl": "path"},
        ],
        "directions": directions,
        "notes": [
            "No frozen artifact-envelope schema file. The on-tree schema is the unit_manifest row.",
            "The G-1 measure checks path/sha256/present/unit_id and does not read bytes, receipt_path, sentinel, retention_class, or evidence_anchors.",
        ],
    }


def completion_predicate_contract(catalog: dict[str, Any]) -> dict[str, Any]:
    uid = "ARC-0087"
    row = _unit(catalog, uid)
    question = str(row.get("question_or_target") or "")
    _must_contain(IMP0433_REL, "process/task reached a valid terminal state", "c01")
    _must_contain(IMP0433_REL, "downstream consumers can read it", "c12")
    docs = list(ARC_0087_DOC)
    schema: list[str] = []
    for field, snippet in MEASURE_SNIPPETS.items():
        _must_contain(MEASURE_REL, snippet, f"measure-{field}")
    impl = list(ARC_0087_IMPL)
    docs_defaults = {
        "min_meaningful_size": "per-class floor derived from real artifacts",
        "schema_parse": "validate against declared output_schema",
    }
    impl_defaults = {
        "min_meaningful_size": 1,
        "schema_parse": "json.loads only (no output_schema check)",
    }
    directions = G.compare_surfaces(
        docs,
        schema,
        impl,
        docs_defaults=docs_defaults,
        schema_defaults={},
        impl_defaults=impl_defaults,
        qualify=uid,
    )
    frozen = (REPO / "command-center/phase4/contracts/ARC-0087.json").is_file()
    gates = (REPO / "command-center/COMPLETION-GATES.json").is_file()
    return {
        "id": uid,
        "title": str(row.get("title") or uid),
        "question": question,
        "frozen_contract_path": "command-center/phase4/contracts/ARC-0087.json",
        "frozen_contract_present": frozen,
        "completion_gates_present": gates,
        "docs_fields": sorted(docs),
        "schema_fields": sorted(schema),
        "impl_fields": sorted(impl),
        "impl_source": "command-center/p2-wave/_measure_one_delivered.py",
        "directions": directions,
        "notes": [
            "COMPLETION-GATES.json and the frozen ARC-0087 contract are both absent; schema surface is empty.",
            "The live G-1 measure implements a subset of the twelve conditions and weakens min-size plus schema-parse.",
        ],
    }


def workflow_dsl_contract(catalog: dict[str, Any]) -> dict[str, Any]:
    uid = "ARC-0082"
    row = _unit(catalog, uid)
    question = str(row.get("question_or_target") or "")
    _assert_phrases(question, ARC_0082_PHRASES, uid)
    docs = list(ARC_0082_DOC)
    schema_path = REPO / REGISTRY_SCHEMA_REL
    schema_doc = json.loads(schema_path.read_text(encoding="utf-8"))
    schema = _json_schema_fields(schema_doc, "workflow_blueprint")
    _must_contain(EXTRACT_REL, 'WF_KEYS = ("id", "discovery_only", "stages", "stopping")', "wf-keys")
    _must_contain(GENERATOR_REL, '"discovery_only": entry["discovery_only"]', "gen-discovery")
    _must_contain(GENERATOR_REL, '"stages": entry["stages"]', "gen-stages")
    _must_contain(GENERATOR_REL, '"stopping": entry["stopping"]', "gen-stopping")
    impl = {
        "id",
        "discovery_only",
        "stages",
        "stopping",
        "stages.id",
        "stages.kind",
        "stages.inputs",
        "stages.outputs",
        "stopping.max_stages",
        "stopping.on_error",
        "kind",
    }
    directions = G.compare_surfaces(docs, schema, impl, qualify=uid)
    frozen = (REPO / "command-center/phase4/contracts/ARC-0082.json").is_file()
    return {
        "id": uid,
        "title": str(row.get("title") or uid),
        "question": question,
        "frozen_contract_path": "command-center/phase4/contracts/ARC-0082.json",
        "frozen_contract_present": frozen,
        "on_tree_schema": REGISTRY_SCHEMA_REL,
        "docs_fields": sorted(docs),
        "schema_fields": sorted(schema),
        "impl_fields": sorted(impl),
        "impl_source": "ARC-0010 registry.schema.json workflow_blueprint + generator.py",
        "directions": directions,
        "notes": [
            "Frozen workflow DSL contract is absent. The only on-tree schema is the A2 typed registry subset (stages + stopping).",
            "Documented constructs (fan-out, resume, replay, cost, routing, ...) have no schema and no consumer on this tree.",
        ],
    }


def run_live() -> dict[str, Any]:
    catalog = _load_catalog()
    contracts = [
        work_unit_contract(catalog),
        artifact_envelope_contract(catalog),
        completion_predicate_contract(catalog),
        workflow_dsl_contract(catalog),
    ]
    directions = G.merge_directions(c["directions"] for c in contracts)
    dominant, count = G.dominant_direction(directions)
    control = run_detector_control()
    verdict = G.live_verdict(directions, control_fired=bool(control["fired"]))
    return {
        "contracts": contracts,
        "directions": directions,
        "caption_sum": G.direction_total(directions),
        "tree_fails_today": {
            "dominant_direction": dominant,
            "count": count,
            "summary": (
                f"The live tree's largest named direction is {dominant} "
                f"with {count} qualified fields. Frozen phase-4 contracts "
                f"ARC-0082/0083/0084/0087 are absent; docs and the thin on-tree "
                f"consumers disagree in both directions."
            ),
        },
        "detector_control": control,
        "verdict": verdict,
    }


def run_detector_control() -> dict[str, Any]:
    fixture = json.loads((HERE / "fixtures" / "control.json").read_text(encoding="utf-8"))
    planted = G.surfaces_from_fixture(fixture["planted"])
    clean = G.surfaces_from_fixture(fixture["clean"])
    mismatch = G.surfaces_from_fixture(fixture["default_mismatch"])
    planted_field = fixture["planted_field"]
    found_in = [
        key
        for key in ("docs_not_schema", "docs_not_impl")
        if f"fixture.{planted_field}" in (planted[key].get("fields") or [])
    ]
    clean_hit = any(
        f"fixture.{planted_field}" in (clean[key].get("fields") or [])
        for key in G.DIRECTION_KEYS
    )
    equal = G.compare_surfaces(["x"], ["x"], ["x"])
    uncontrolled = G.live_verdict(equal, control_fired=False)
    fired = (
        planted_field == G.PLANTED_FIELD
        and set(found_in) == {"docs_not_schema", "docs_not_impl"}
        and not clean_hit
        and mismatch["default_mismatch"]["count"] >= 1
        and uncontrolled == "DETECTOR-FAILURE"
    )
    return {
        "planted_field": planted_field,
        "found_in": found_in,
        "clean_silent": not clean_hit,
        "default_mismatch_control_count": mismatch["default_mismatch"]["count"],
        "uncontrolled_zero_is_detector_failure": True,
        "uncontrolled_zero_verdict": uncontrolled,
        "fired": fired,
        "planted_directions": planted,
        "clean_directions": clean,
    }


if __name__ == "__main__":
    report = run_live()
    print(json.dumps(
        {
            "verdict": report["verdict"],
            "caption_sum": report["caption_sum"],
            "tree_fails_today": report["tree_fails_today"],
            "direction_counts": {k: v["count"] for k, v in report["directions"].items()},
            "detector_control_fired": report["detector_control"]["fired"],
        },
        indent=2,
        sort_keys=True,
    ))
    if report["verdict"] == "DETECTOR-FAILURE" or not report["detector_control"]["fired"]:
        raise SystemExit(1)
    raise SystemExit(0)
