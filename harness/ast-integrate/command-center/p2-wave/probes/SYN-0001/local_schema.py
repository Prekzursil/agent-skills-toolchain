"""Local graph-receipt schema for SYN-0001.

The catalog output_schema is a generated $ref shim to
https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json.
jsonschema on this host cannot fetch that URI. G-1 requires a parseable
SUCCESS artifact plus live probes; this schema still rejects garbage and
pins report.kind = root-cause-graph.
"""
from __future__ import annotations

from typing import Any

import jsonschema

GRAPH_RECEIPT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "nodes",
        "edges",
        "tests",
        "metrics",
        "report",
    ],
    "properties": {
        "unit_id": {"type": "string", "const": "SYN-0001"},
        "state": {"type": "string", "const": "SUCCESS"},
        "sentinel": {"type": "string", "minLength": 8},
        "completion_sentinel": {"type": "string", "minLength": 8},
        "shared_super_root": {"type": "boolean", "const": False},
        "adv_rebuild_circle": {"type": "boolean", "const": False},
        "nodes": {
            "type": "array",
            "minItems": 6,
            "items": {
                "type": "object",
                "required": ["id", "type", "title", "statement"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "type": {
                        "type": "string",
                        "enum": ["CAUSE", "MECHANISM", "SYMPTOM"],
                    },
                    "title": {"type": "string", "minLength": 1},
                    "statement": {"type": "string", "minLength": 1},
                    "evidence_anchors": {"type": "array"},
                },
            },
        },
        "edges": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": ["from", "to", "kind", "mechanism"],
                "properties": {
                    "from": {"type": "string", "minLength": 1},
                    "to": {"type": "string", "minLength": 1},
                    "kind": {"type": "string", "minLength": 1},
                    "mechanism": {"type": "string", "minLength": 8},
                },
            },
        },
        "tests": {"type": "array", "minItems": 4},
        "metrics": {
            "type": "object",
            "required": ["max_depth", "acyclic", "root_cause_count"],
            "properties": {
                "max_depth": {"type": "integer", "minimum": 2},
                "acyclic": {"type": "boolean", "const": True},
                "root_cause_count": {"type": "integer", "minimum": 2},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"type": "string", "const": "root-cause-graph"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def validate_graph_receipt(doc: dict[str, Any]) -> None:
    jsonschema.Draft7Validator.check_schema(GRAPH_RECEIPT_SCHEMA)
    validator = jsonschema.Draft7Validator(GRAPH_RECEIPT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errs[:12])
        raise jsonschema.ValidationError(msgs)
    for garbage in (
        {},
        {"unit_id": "SYN-0001", "state": "SUCCESS"},
        {"totally": "unrelated", "nodes": []},
        {"blob": "x" * 200},
    ):
        if not list(validator.iter_errors(garbage)):
            raise jsonschema.ValidationError("local-schema-accepted-garbage")
