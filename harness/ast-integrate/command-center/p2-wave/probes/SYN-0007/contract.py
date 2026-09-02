"""Local ranking contract for SYN-0007.

The catalog output_schema is a generated $ref shim to
https://ast-integrate.invalid/... . Distro jsonschema 4.10 fetches that URL and
raises RefResolutionError. G-1 measure only json.loads the artifact; named
probes own the ranking shape (prevented_claim_ids, hierarchy depth, sort_key).
"""
from __future__ import annotations

from typing import Any

import jsonschema

RANKING_ROW = {
    "type": "object",
    "required": [
        "rank",
        "cause_id",
        "intervention_id",
        "action",
        "available_at_phase",
        "spec_line",
        "prevented_claim_ids",
        "subtree_size",
        "severity",
        "cost_seconds",
        "cost_basis",
        "score_micro",
        "sort_key",
    ],
    "properties": {
        "rank": {"type": "integer", "minimum": 1},
        "cause_id": {"type": "string", "minLength": 1},
        "intervention_id": {"type": "string", "minLength": 1},
        "action": {"type": "string", "minLength": 1},
        "available_at_phase": {"type": "string", "minLength": 1},
        "spec_line": {"type": "string", "minLength": 8},
        "prevented_claim_ids": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "subtree_size": {"type": "integer", "minimum": 1},
        "severity": {"enum": ["P0", "P1", "P2", "P3"]},
        "cost_seconds": {"type": "integer", "minimum": 1},
        "cost_basis": {"enum": ["DERIVED", "ESTIMATE"]},
        "estimate_band": {
            "type": ["string", "null"],
            "enum": ["XS", "S", "M", "L", "XL", None],
        },
        "score_micro": {"type": "integer"},
        "sort_key": {"type": "array", "minItems": 4, "maxItems": 4},
    },
    "allOf": [
        {
            "if": {
                "properties": {"cost_basis": {"const": "ESTIMATE"}},
                "required": ["cost_basis"],
            },
            "then": {
                "required": ["estimate_band"],
                "properties": {
                    "estimate_band": {"enum": ["XS", "S", "M", "L", "XL"]},
                },
            },
        }
    ],
}

LOCAL_CONTRACT = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "kind",
        "question",
        "ranking",
        "hierarchy",
        "tests",
        "rejected",
        "cost_model",
        "named_probes",
    ],
    "properties": {
        "unit_id": {"const": "SYN-0007"},
        "state": {"enum": ["SUCCESS"]},
        "kind": {"const": "intervention-ranking"},
        "sentinel": {"type": "string", "minLength": 32},
        "completion_sentinel": {"type": "string", "minLength": 32},
        "question": {"type": "string", "minLength": 16},
        "ranking": {"type": "array", "minItems": 3, "items": RANKING_ROW},
        "hierarchy": {
            "type": "object",
            "required": ["nodes", "edges", "max_depth", "acyclic"],
            "properties": {
                "nodes": {"type": "array", "minItems": 4},
                "edges": {"type": "array", "minItems": 3},
                "max_depth": {"type": "integer", "minimum": 2},
                "acyclic": {"const": True},
            },
        },
        "tests": {"type": "array", "minItems": 3},
        "rejected": {"type": "array"},
        "cost_model": {
            "type": "object",
            "required": ["formula", "estimate_bands_seconds"],
        },
        "named_probes": {"type": "array", "minItems": 2},
    },
}

_GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "SYN-0007", "state": "SUCCESS"},
)


def validate_ranking_doc(doc: dict[str, Any]) -> list[str]:
    jsonschema.Draft7Validator.check_schema(LOCAL_CONTRACT)
    validator = jsonschema.Draft7Validator(LOCAL_CONTRACT)
    msgs = [
        f"{list(err.path)}: {err.message}"
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]
    for garbage in _GARBAGE:
        if not list(validator.iter_errors(garbage)):
            msgs.append(f"accepted-garbage:{list(garbage)[:2]}")
    return msgs
