"""Disk-local Draft-07 contract for AUD-0074.

The catalog output_schema at command-center/schema/audit-graph.schema.json is a
generated $ref shim whose target is https://ast-integrate.invalid/... .
jsonschema 4.10.3 on this worktree uses RefResolver and tries the network
(RefResolutionError). G-1 does not require that fetch. This module compiles a
local Draft-07 contract with no $ref, so it still rejects garbage and encodes
the probe-checked lineage facts. It does not rebuild the catalog shim
(no ADV schema-rebuild loop).
"""
from __future__ import annotations

from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/audit-graph.schema.json"
UNIT = "AUD-0074"

LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "kind",
        "question",
        "answer",
        "nodes",
        "edges",
        "stale_downstream",
        "headline",
        "corrections",
        "tests",
        "negative_controls",
        "evidence",
        "reviewer",
        "artifacts",
        "report",
    ],
    "properties": {
        "unit_id": {"const": UNIT},
        "state": {"const": "SUCCESS"},
        "sentinel": {
            "type": "string",
            "minLength": 16,
            "pattern": "^SUCCESS:AUD-0074",
        },
        "completion_sentinel": {
            "type": "string",
            "minLength": 40,
            "pattern": "^SUCCESS:AUD-0074",
        },
        "kind": {"const": "audit-graph"},
        "question": {"type": "string", "minLength": 20},
        "answer": {"type": "string", "minLength": 40},
        "nodes": {"type": "array", "minItems": 29},
        "edges": {"type": "array", "minItems": 8},
        "stale_downstream": {"type": "array", "minItems": 1},
        "corrections": {"type": "array", "minItems": 1},
        "headline": {
            "type": "object",
            "required": [
                "node_count",
                "citation_edge_count",
                "stale_downstream_count",
                "doc13_stale_downstream_count",
                "doc13_stale_artifacts",
            ],
            "properties": {
                "node_count": {"type": "integer", "minimum": 29},
                "citation_edge_count": {"type": "integer", "minimum": 8},
                "stale_downstream_count": {"type": "integer", "minimum": 1},
                "doc13_stale_downstream_count": {"type": "integer", "minimum": 1},
                "doc13_stale_artifacts": {"type": "array", "minItems": 1},
            },
        },
        "tests": {"type": "array", "minItems": 1},
        "negative_controls": {"type": "array", "minItems": 1},
        "evidence": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "artifacts": {"type": "array", "minItems": 1},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "audit-graph"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def catalog_schema_on_disk() -> bool:
    return (REPO / CATALOG_SCHEMA).is_file() and (REPO / CATALOG_SCHEMA).stat().st_size > 0


def make_validator() -> jsonschema.Draft7Validator:
    def blocked(uri: str):
        raise jsonschema.exceptions.RefResolutionError(f"blocked-remote:{uri}")

    resolver = jsonschema.RefResolver.from_schema(
        LOCAL_SCHEMA,
        store={},
        handlers={"http": blocked, "https": blocked},
    )
    return jsonschema.Draft7Validator(LOCAL_SCHEMA, resolver=resolver)


def iter_errors(doc: object) -> list:
    return sorted(make_validator().iter_errors(doc), key=lambda e: list(e.path))


def garbage_error_count(sample: object | None = None) -> int:
    return sum(1 for _ in make_validator().iter_errors(sample if sample is not None else {"nope": 1}))
