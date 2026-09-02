#!/usr/bin/env python3
"""Author command-center/schema/receipt.schema.json for IMP-0433.

Keeps existing fragment $defs (portability_report, matrix_cell, benchmark_result)
so already-delivered TST units that $ref those fragments stay valid. Adds
$defs/receipt_core and makes the document root $ref that definition.

Does not rebuild platform/schema (absent here; no ADV rebuild circle).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/receipt.schema.json"
SCHEMA_PATH = REPO / SCHEMA_REL

KEEP_DEFS = ("portability_report", "matrix_cell", "benchmark_result")

RECEIPT_CORE = {
    "title": "Program receipt (receipt_core)",
    "description": (
        "Strict enough that a SUCCESS receipt missing sentinel, evidence "
        "anchors, or reviewer verdict is INVALID. Permissive enough that a "
        "catalog unit can satisfy it by emitting the required fields. "
        "additionalProperties is false so an unknown top-level key is a "
        "schema-parse failure (completion condition 4)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "artifacts",
        "evidence",
        "min_bytes_threshold",
    ],
    "properties": {
        "schema_version": {"type": "integer", "minimum": 1},
        "unit_id": {
            "type": "string",
            "minLength": 7,
            "pattern": "^[A-Z]{2,5}-[0-9]{4}$",
        },
        "id": {"type": "string", "minLength": 2},
        "state": {
            "type": "string",
            "enum": [
                "SUCCESS",
                "PARTIAL",
                "BLOCKED",
                "FAILED",
                "TIMEOUT",
                "SEVERED",
            ],
        },
        "sentinel": {"type": "string", "minLength": 8},
        "completion_sentinel": {"type": "string", "minLength": 8},
        "spec_anchor": {"type": "string"},
        "spec_source": {"type": "string"},
        "spec_inputs_present": {"type": "object"},
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "profile": {"type": "string"},
        "produced_by": {"type": "object"},
        "artifacts": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["path", "exists"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "exists": {"const": True},
                    "bytes": {"type": "integer", "minimum": 0},
                    "sha256": {"type": "string"},
                    "role": {"type": "string"},
                    "eol": {"type": "string"},
                    "note": {"type": "string"},
                },
            },
        },
        "evidence": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["claim", "verdict"],
                "properties": {
                    "claim": {"type": "string", "minLength": 1},
                    "verdict": {"type": "string", "minLength": 1},
                    "anchor": {"type": "string"},
                    "confidence": {"type": "string"},
                    "probes": {"type": "array"},
                    "kind": {"type": "string"},
                    "path": {"type": "string"},
                    "line": {"type": "integer"},
                    "snippet": {"type": "string"},
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "detail": {"type": "string"},
                },
            },
        },
        "evidence_anchors": {"type": "array"},
        "evidence_requirement": {"type": "string"},
        "timestamps": {"type": "object"},
        "retry": {"type": "object"},
        "tests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["id", "result"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "command": {"type": "string"},
                    "name": {"type": "string"},
                    "result": {
                        "type": "string",
                        "enum": ["PASS", "FAIL", "NOT-RUN"],
                    },
                    "assertions": {"type": "integer"},
                    "output_tail": {"type": "string"},
                    "exit_code": {"type": "integer"},
                    "raw_output": {"type": "string"},
                },
            },
        },
        "tests_required": {"type": "string"},
        "negative_controls": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string"},
                    "description": {"type": "string"},
                    "fired_on_bad_state": {"type": "boolean"},
                    "silent_on_good_state": {"type": "boolean"},
                    "bad_state_output": {"type": "string"},
                    "good_state_output": {"type": "string"},
                },
            },
        },
        "reviewer": {
            "type": "object",
            "additionalProperties": True,
            "required": ["reviewer_id", "verdict"],
            "properties": {
                "reviewer_id": {"type": "string", "minLength": 3},
                "verdict": {
                    "type": "string",
                    "enum": ["PASS", "FAIL", "NOT-REVIEWED"],
                },
                "independent": {"type": "boolean"},
                "fresh_context": {"type": "boolean"},
                "notes": {"type": "string"},
            },
        },
        "reviewer_verdict": {"type": "string"},
        "reviewer_requirement": {"type": "string"},
        "manifest_registration": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "registered": {"type": "boolean"},
                "manifest_path": {"type": "string"},
            },
        },
        "downstream_consumers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "consumer": {"type": "string"},
                    "artifact_path": {"type": "string"},
                    "executed": {"type": "boolean"},
                    "read_ok": {"type": "boolean"},
                    "exit_code": {"type": "integer"},
                    "probe": {"type": "object"},
                },
            },
        },
        "residual_unknowns": {"type": "array"},
        "failure": {"type": "object"},
        "report": {"type": "object"},
        "defects": {"type": "array"},
        "title": {"type": "string"},
        "question": {"type": "string"},
        "question_or_target": {"type": "string"},
        "answer": {"type": "string"},
        "notes": {"type": "string"},
        "named_probes": {"type": "array"},
        "cloud_ok": {"type": "boolean"},
        "registered": {"type": "boolean"},
        "output_path": {"type": "string"},
        "output_schema": {"type": "string"},
        "status": {"type": "string"},
        "ts": {"type": "string"},
        "probe_results": {"type": "object"},
        "report_kind": {"type": "string"},
        "catalog": {"type": "object"},
        "fixture_matrix": {"type": "array"},
        "scope": {"type": "object"},
        "anti_patterns": {"type": "array"},
        "condition_texts": {"type": "array"},
        "condition_table": {"type": "array"},
        "completion_verdict": {"type": "object"},
        "library_path": {"type": "string"},
        "canonical_module": {"type": "string"},
        "canonical_symbol": {"type": "string"},
        "premise_refuted": {"type": "boolean"},
        "named_strictness": {"type": "object"},
        "inputs": {"type": "array"},
        "phase": {"type": ["string", "integer"]},
        "host": {"type": "object"},
        "compatibility_report": {"type": "object"},
        "manifest_path": {"type": "string"},
    },
    "allOf": [
        {
            "if": {
                "properties": {"state": {"const": "SUCCESS"}},
                "required": ["state"],
            },
            "then": {
                "required": [
                    "reviewer",
                    "tests",
                    "negative_controls",
                    "manifest_registration",
                    "downstream_consumers",
                ],
                "properties": {
                    "evidence": {"type": "array", "minItems": 2},
                    "reviewer": {
                        "type": "object",
                        "required": ["reviewer_id", "verdict", "independent"],
                        "properties": {
                            "reviewer_id": {"type": "string", "minLength": 3},
                            "verdict": {"const": "PASS"},
                            "independent": {"const": True},
                        },
                    },
                    "tests": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {"result": {"const": "PASS"}},
                        },
                    },
                    "negative_controls": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["fired_on_bad_state"],
                            "properties": {
                                "fired_on_bad_state": {"const": True}
                            },
                        },
                    },
                    "manifest_registration": {
                        "type": "object",
                        "required": ["registered"],
                        "properties": {"registered": {"const": True}},
                    },
                    "downstream_consumers": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["executed"],
                            "properties": {"executed": {"const": True}},
                        },
                    },
                },
                "not": {
                    "required": ["defects"],
                    "properties": {
                        "defects": {
                            "type": "array",
                            "contains": {
                                "type": "object",
                                "required": ["severity", "status"],
                                "properties": {
                                    "severity": {"enum": ["P0", "P1"]},
                                    "status": {"enum": ["open", "OPEN"]},
                                },
                            },
                        }
                    },
                },
            },
        }
    ],
}


def load_keep_defs() -> dict:
    current = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    defs = current.get("$defs") or current.get("definitions") or {}
    keep = {k: defs[k] for k in KEEP_DEFS if k in defs}
    missing = [k for k in KEEP_DEFS if k not in keep]
    if missing:
        raise SystemExit(f"FAILED:IMP-0433 missing fragment $defs {missing}")
    return keep


def build_schema() -> dict:
    keep = load_keep_defs()
    # Flatten receipt_core onto the document root. A top-level $ref plus the
    # relative $id "command-center/schema/receipt.schema.json" makes this
    # jsonschema 4.10 resolver request a non-URI path. Fragments stay in $defs.
    core = dict(RECEIPT_CORE)
    core.pop("title", None)
    core.pop("description", None)
    defs = {"receipt_core": RECEIPT_CORE, **keep}
    doc = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/schema/receipt.schema.json",
        "title": "Program receipts (receipt_core plus live TST fragments)",
        "description": (
            "IMP-0433 authored receipt_core so a receipt missing its "
            "sentinel, evidence anchors, or reviewer verdict is INVALID. "
            "Fragment $defs portability_report / matrix_cell / benchmark_result "
            "are preserved for units that $ref them."
        ),
        "$comment": "SENTINEL:IMP-0433:RECEIPT-SCHEMA-AUTHORED",
    }
    doc.update(core)
    doc["$defs"] = defs
    doc["definitions"] = {
        "receipt_core": {"$ref": "#/$defs/receipt_core"},
        "portability_report": {"$ref": "#/$defs/portability_report"},
        "matrix_cell": {"$ref": "#/$defs/matrix_cell"},
        "benchmark_result": {"$ref": "#/$defs/benchmark_result"},
    }
    return doc


def main() -> int:
    doc = build_schema()
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    size = SCHEMA_PATH.stat().st_size
    print(f"wrote {SCHEMA_REL} bytes={size}")
    print("SUCCESS:IMP-0433 author_schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
