"""Local structural schema for the CNL-0057 design note.

The catalog output_schema is a generated $ref shim to
https://ast-integrate.invalid/... which does not resolve on this host.
G-1 parses JSON and re-runs named probes; it does not fetch that URL.
This schema still rejects garbage and pins the load-bearing fields.
"""
from __future__ import annotations

from typing import Any

import jsonschema

LOCAL_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "kind",
        "answer",
        "vote_harmful_decision_types",
        "synthesis_only_owes",
        "method_disagreement_fixture",
        "evidence",
        "tests",
        "negative_controls",
        "reviewer",
        "artifacts",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "unit_id": {"const": "CNL-0057"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0057"},
        "completion_sentinel": {"const": "SUCCESS:CNL-0057"},
        "kind": {"const": "council-design-note"},
        "answer": {"type": "string", "minLength": 200},
        "vote_harmful_decision_types": {"type": "array", "minItems": 4},
        "synthesis_only_owes": {"type": "array", "minItems": 4},
        "method_disagreement_fixture": {
            "type": "object",
            "required": ["disagree", "reason", "vote_winner", "synthesis_winner"],
        },
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent", "counterexample"],
        },
        "artifacts": {"type": "array", "minItems": 1},
    },
}


def validator() -> jsonschema.Draft7Validator:
    return jsonschema.Draft7Validator(LOCAL_SCHEMA)


def iter_errors(doc: dict[str, Any]) -> list[str]:
    v = validator()
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    ]


def rejects_garbage() -> bool:
    v = validator()
    probes = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    return all(bool(list(v.iter_errors(p))) for p in probes)
