"""Offline schema for TST-0049.

Catalog output_schema command-center/schema/conformance-report.schema.json is a
generated $ref shim to https://ast-integrate.invalid/... . jsonschema 4.10.3
RefResolver tries the network and raises RefResolutionError. G-1 does not
require that hop and forbids an ADV rebuild of the catalog shim. This draft-07
schema still rejects garbage and pins the probe-visible receipt fields.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/conformance-report.schema.json"

REQUIRED_NEGATIVE_IDS = (
    "blank-cell",
    "supported-without-evidence",
    "untested-as-pass",
    "untested-missing-token",
    "inferred-as-supported",
    "installer-exit-as-run",
    "unpinned-supported",
    "all-green-partial-estate",
    "failed-without-run-or-untested",
)

LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "live_audit",
        "comparison_table",
        "negative_controls",
        "tests",
        "answer",
        "reviewer",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "TST-0049"},
        "id": {"const": "TST-0049"},
        "report_kind": {"const": "conformance-report"},
        "state": {"enum": ["SUCCESS"]},
        "sentinel": {"const": "SUCCESS:TST-0049"},
        "completion_sentinel": {"const": "SUCCESS:TST-0049"},
        "answer": {"type": "string", "minLength": 64, "pattern": "UNTESTED"},
        "live_audit": {
            "type": "object",
            "required": [
                "blank",
                "untested",
                "asserted_without_evidence",
                "every_cell_has_run_id_or_untested",
                "declared",
                "present",
            ],
            "properties": {
                "blank": {"type": "integer", "minimum": 0, "maximum": 0},
                "untested": {"type": "integer", "minimum": 1},
                "asserted_without_evidence": {"type": "integer", "minimum": 0},
                "declared": {"type": "integer", "minimum": 1},
                "present": {"type": "integer", "minimum": 1},
                "every_cell_has_run_id_or_untested": {"const": True},
            },
        },
        "comparison_table": {"type": "array", "minItems": 10},
        "coverage_table": {"type": "array", "minItems": 1},
        "negative_controls": {
            "type": "array",
            "minItems": 9,
            "items": {
                "type": "object",
                "required": ["id", "fired_on_bad_state", "silent_on_good_state"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "fired_on_bad_state": {"const": True},
                    "silent_on_good_state": {"const": True},
                },
            },
        },
        "tests": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "required": ["id", "result"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "result": {"const": "PASS"},
                },
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "evidence": {"type": "array", "minItems": 2},
    },
}


def catalog_shim_present() -> dict:
    path = REPO / CATALOG_SCHEMA
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:TST-0049 catalog schema missing {CATALOG_SCHEMA}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("x-artifact-class") != "conformance-report":
        raise SystemExit("FAILED:TST-0049 catalog schema class is not conformance-report")
    if "$ref" not in doc:
        raise SystemExit("FAILED:TST-0049 catalog schema lost its shim $ref")
    return doc


def validator() -> jsonschema.Draft7Validator:
    jsonschema.Draft7Validator.check_schema(LOCAL_SCHEMA)
    return jsonschema.Draft7Validator(LOCAL_SCHEMA)


def errors(doc) -> list:
    return list(validator().iter_errors(doc))


def missing_negative_ids(doc: dict) -> list[str]:
    have = {
        n.get("id")
        for n in (doc.get("negative_controls") or [])
        if isinstance(n, dict)
    }
    return [fid for fid in REQUIRED_NEGATIVE_IDS if fid not in have]
