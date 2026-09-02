#!/usr/bin/env python3
"""Shared loaders for the WFA-0001 schema pack and its bundled examples."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"
PACK_PATH = REPO / PACK_REL
SENTINEL = "SUCCESS:WFA-0001"

RECORD_TYPES = (
    "WorkflowRecord",
    "SweepReport",
    "ProbeReport",
    "ExtractionReport",
    "DispositionRecord",
    "Graph",
    "WorkflowIR",
    "AdapterConformanceReport",
    "SemanticDiff",
    "FusionResult",
    "BenchmarkResult",
    "CertificationRecord",
    "RegressionFixture",
    "AuditReport",
    "HandoffContract",
    "MechanismRecord",
    "RepairRecord",
    "CoverageMatrix",
)

EXTRA_KEY = "not_a_declared_property"


def load_pack(path: Path | None = None) -> dict[str, Any]:
    target = path or PACK_PATH
    if not target.is_file() or target.stat().st_size <= 0:
        raise FileNotFoundError(f"schema pack missing: {target}")
    doc = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("schema pack is not an object")
    return doc


def defs_of(pack: dict[str, Any]) -> dict[str, Any]:
    defs = pack.get("$defs")
    if not isinstance(defs, dict):
        raise ValueError("schema pack has no $defs object")
    return defs


def bundled_examples(defn: dict[str, Any], name: str) -> tuple[Any, Any]:
    valid = defn.get("x-valid-example")
    if valid is None:
        examples = defn.get("examples")
        if isinstance(examples, list) and examples:
            valid = examples[0]
    invalid = defn.get("x-invalid-example")
    if valid is None or invalid is None:
        raise ValueError(f"{name} missing bundled valid/invalid example")
    return valid, invalid


def assert_additional_properties_false(pack: dict[str, Any]) -> list[str]:
    """Code assertion: each of the 18 $defs sets additionalProperties:false."""
    defs = defs_of(pack)
    missing = [n for n in RECORD_TYPES if n not in defs]
    if missing:
        raise AssertionError(f"$defs missing {missing}")
    failed: list[str] = []
    for name in RECORD_TYPES:
        defn = defs[name]
        if not isinstance(defn, dict) or defn.get("additionalProperties") is not False:
            failed.append(name)
    if failed:
        raise AssertionError(
            "additionalProperties:false does not hold on $defs: " + ", ".join(failed)
        )
    extra = sorted(set(defs) - set(RECORD_TYPES))
    if extra:
        raise AssertionError(f"$defs has unexpected names: {extra}")
    return list(RECORD_TYPES)


def delete_first_required(instance: Any, defn: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(instance, dict):
        raise TypeError("valid example must be an object")
    required = defn.get("required")
    if not isinstance(required, list) or not required:
        raise ValueError("definition has no required keys")
    key = str(required[0])
    mutant = dict(instance)
    if key not in mutant:
        raise KeyError(f"valid example missing required key {key}")
    del mutant[key]
    return key, mutant
