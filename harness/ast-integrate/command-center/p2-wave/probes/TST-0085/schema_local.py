"""Per-unit schema for TST-0085.

The catalog file command-center/schema/benchmark-receipt.schema.json is a
GENERATED SHIM whose $ref points at https://ast-integrate.invalid/... .
jsonschema 4.10.3 RefResolver tries the network and does not constrain the
receipt; a naive Draft7Validator(shim) therefore neither accepts a real
artifact nor rejects garbage. This module is the load-bearing schema.

Do not overwrite the shared catalog shim (no ADV schema-rebuild circle).
"""
from __future__ import annotations

from typing import Any

import jsonschema

LOCAL_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ast-integrate.invalid/command-center/p2-wave/probes/TST-0085/receipt.schema.json",
    "title": "TST-0085 top-k injection budget receipt",
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "budget",
        "raw_runs",
        "installed_counts",
        "variance_band",
        "flood_control",
        "tests",
        "reviewers",
    ],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "unit_id": {"type": "string", "const": "TST-0085"},
        "state": {"type": "string", "minLength": 1},
        "sentinel": {
            "type": "string",
            "pattern": "^SUCCESS:TST-0085",
        },
        "installed_counts": {
            "type": "array",
            "minItems": 3,
            "items": {"type": "integer"},
        },
        "budget": {
            "type": "object",
            "required": ["held", "at_500_max_injected_tokens", "ceiling"],
            "properties": {
                "held": {"type": "boolean"},
                "at_500_max_injected_tokens": {"type": "integer", "minimum": 0},
                "ceiling": {"type": "integer", "minimum": 1},
            },
        },
        "raw_runs": {
            "type": "array",
            "minItems": 9,
            "items": {
                "type": "object",
                "required": ["installed_count", "query_id", "injected_tokens"],
                "properties": {
                    "installed_count": {"type": "integer"},
                    "query_id": {"type": "string", "minLength": 1},
                    "injected_tokens": {"type": "integer", "minimum": 0},
                },
            },
        },
        "variance_band": {
            "type": "object",
            "required": [
                "derived_from",
                "n",
                "mean",
                "sample_variance",
                "sample_std",
                "ci95_low",
                "ci95_high",
            ],
            "properties": {
                "derived_from": {"type": "string", "const": "raw_runs"},
                "n": {"type": "integer", "minimum": 2},
                "mean": {"type": "number"},
                "sample_variance": {"type": "number", "minimum": 0},
                "sample_std": {"type": "number", "minimum": 0},
                "ci95_low": {"type": "number"},
                "ci95_high": {"type": "number"},
            },
        },
        "flood_control": {
            "type": "object",
            "required": [
                "unbounded_exceeds_ceiling",
                "unbounded_growth_is_linear",
                "unbounded_at_500",
            ],
            "properties": {
                "unbounded_exceeds_ceiling": {"type": "boolean"},
                "unbounded_growth_is_linear": {"type": "boolean"},
                "unbounded_at_500": {"type": "integer", "minimum": 0},
            },
        },
        "tests": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["id", "result"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "result": {"type": "string", "minLength": 1},
                },
            },
        },
        "reviewers": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["role", "reviewer_id", "verdict"],
                "properties": {
                    "role": {"type": "string", "minLength": 1},
                    "reviewer_id": {"type": "string", "minLength": 1},
                    "verdict": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}


def validator() -> jsonschema.Draft7Validator:
    jsonschema.Draft7Validator.check_schema(LOCAL_SCHEMA)
    return jsonschema.Draft7Validator(LOCAL_SCHEMA)
