#!/usr/bin/env python3
"""Local non-vacuous contract for TST-0088's fault-injection-receipt shim.

The catalog output_schema (command-center/schema/fault-injection-receipt.schema.json)
is a generated $ref shim. jsonschema 4.10 follows that $ref over HTTPS to
ast-integrate.invalid and raises RefResolutionError. G-1 requires the artifact
to parse as JSON and carry SUCCESS:TST-0088; this contract still rejects garbage
and pins the live SIGKILL / condition-5 / atomic-invisible fields the probes
re-check.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/fault-injection-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0088"

CONTRACT: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "classification",
        "truncated_fixture",
        "atomic_fix",
        "both_states",
        "tests",
        "evidence",
        "named_probes",
        "artifacts",
        "negative_controls",
    ],
    "properties": {
        "unit_id": {"const": "TST-0088"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": SENTINEL},
        "classification": {
            "type": "object",
            "required": [
                "verdict",
                "condition_id",
                "never_success",
                "truncated_exists",
                "truncated_parses",
                "truncated_looks_plausible",
            ],
            "properties": {
                "verdict": {"const": "FAILED"},
                "condition_id": {"const": 5},
                "never_success": {"const": True},
                "truncated_exists": {"const": True},
                "truncated_parses": {"const": True},
                "truncated_looks_plausible": {"const": True},
            },
        },
        "truncated_fixture": {
            "type": "object",
            "required": ["path", "bytes", "sha256", "parses", "sentinel_present"],
            "properties": {
                "path": {
                    "const": (
                        "command-center/p2-wave/probes/TST-0088/"
                        "fixtures/truncated-partial.json"
                    )
                },
                "bytes": {"type": "integer", "minimum": 64},
                "sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "parses": {"const": True},
                "sentinel_present": {"const": False},
            },
        },
        "atomic_fix": {
            "type": "object",
            "required": [
                "destination_visible_after_sigkill",
                "published_partial",
                "uninterrupted_verdict",
            ],
            "properties": {
                "destination_visible_after_sigkill": {"const": False},
                "published_partial": {"const": False},
                "uninterrupted_verdict": {"const": "SUCCESS"},
            },
        },
        "both_states": {
            "type": "object",
            "required": [
                "truncated_verdict",
                "complete_streaming_verdict",
                "absent_condition_id",
                "atomic_complete_verdict",
            ],
            "properties": {
                "truncated_verdict": {"const": "FAILED"},
                "complete_streaming_verdict": {"const": "SUCCESS"},
                "absent_condition_id": {"const": 2},
                "atomic_complete_verdict": {"const": "SUCCESS"},
            },
        },
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
        "named_probes": {"type": "array", "minItems": 2},
        "artifacts": {"type": "array", "minItems": 1},
        "negative_controls": {"type": "array", "minItems": 1},
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
    },
}

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000, "state": "SUCCESS"},
)


def catalog_schema_present() -> bool:
    path = REPO / SCHEMA_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(doc, dict) and bool(doc.get("$ref") or doc.get("$id"))


def validate_doc(doc: dict) -> list[str]:
    errs: list[str] = []
    if not catalog_schema_present():
        errs.append(f"catalog output_schema missing or empty: {SCHEMA_REL}")
    validator = jsonschema.Draft7Validator(CONTRACT)
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        errs.append(f"{loc}: {err.message}")
    blob = json.dumps(doc, sort_keys=True)
    if SENTINEL not in blob:
        errs.append("completion_sentinel missing from document")
    return errs


def contract_rejects_garbage() -> bool:
    validator = jsonschema.Draft7Validator(CONTRACT)
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            return False
    return True
