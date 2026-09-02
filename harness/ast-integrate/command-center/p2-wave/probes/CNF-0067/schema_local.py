"""Offline schema for CNF-0067.

Catalog output_schema is a generated $ref shim to
https://ast-integrate.invalid/... . jsonschema 4.10.3 RefResolver tries
the network. G-1 does not require that hop and forbids an ADV rebuild of
command-center/schema/dedup-audit.schema.json. This draft-07 schema still
rejects garbage and pins every sampled edge to an independent verdict
plus a mechanical score.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/dedup-audit.schema.json"

LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "brief_was_blind",
        "sampled_edges",
        "disagreement_rate",
        "leak_control",
        "answer",
        "reviewer",
        "tests",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0067"},
        "kind": {"const": "dedup-audit"},
        "state": {"enum": ["SUCCESS"]},
        "brief_was_blind": {"const": True},
        "sentinel": {"type": "string", "minLength": 16, "pattern": "^SUCCESS:CNF-0067"},
        "disagreement_rate": {"type": "number", "minimum": 0, "maximum": 1},
        "sampled_edges": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": [
                    "edge_id",
                    "independent_verdict",
                    "mechanical_score",
                    "mechanical_verdict",
                    "original_verdict",
                    "reported_first",
                    "verdicts_in_order",
                    "evidence",
                ],
                "properties": {
                    "edge_id": {"type": "string", "minLength": 1},
                    "independent_verdict": {"enum": ["DUPLICATE", "DISTINCT"]},
                    "mechanical_verdict": {"enum": ["DUPLICATE", "DISTINCT"]},
                    "original_verdict": {"enum": ["DUPLICATE", "DISTINCT"]},
                    "mechanical_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "reported_first": {"enum": ["mechanical", "independent"]},
                    "verdicts_in_order": {"type": "array", "minItems": 2},
                    "evidence": {
                        "type": "object",
                        "required": [
                            "independent_verdict",
                            "original_verdict",
                            "mechanism_text",
                        ],
                        "properties": {
                            "independent_verdict": {
                                "enum": ["DUPLICATE", "DISTINCT"]
                            },
                            "original_verdict": {"enum": ["DUPLICATE", "DISTINCT"]},
                            "mechanism_text": {
                                "type": "object",
                                "required": ["from", "to"],
                                "properties": {
                                    "from": {"type": "string", "minLength": 8},
                                    "to": {"type": "string", "minLength": 8},
                                },
                            },
                        },
                    },
                },
            },
        },
        "leak_control": {
            "type": "object",
            "required": ["passed", "injected_leaks"],
            "properties": {"passed": {"const": True}},
        },
        "answer": {"type": "string", "minLength": 64, "pattern": "SUCCESS:CNF-0067"},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "tests": {"type": "array", "minItems": 3},
    },
}


def catalog_shim_present() -> dict:
    path = REPO / CATALOG_SCHEMA
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:CNF-0067 catalog schema missing {CATALOG_SCHEMA}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("x-artifact-class") != "dedup-audit":
        raise SystemExit("FAILED:CNF-0067 catalog schema class is not dedup-audit")
    if "$ref" not in doc:
        raise SystemExit("FAILED:CNF-0067 catalog schema lost its shim $ref")
    return doc


def validator() -> jsonschema.Draft7Validator:
    jsonschema.Draft7Validator.check_schema(LOCAL_SCHEMA)
    return jsonschema.Draft7Validator(LOCAL_SCHEMA)


def errors(doc) -> list:
    return list(validator().iter_errors(doc))
