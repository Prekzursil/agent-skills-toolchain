"""Local non-vacuous contract for the CNL-0041 design note.

The catalog output_schema is a generated $ref shim onto
https://ast-integrate.invalid/... . jsonschema 4.10 fetches that URI and
raises RefResolutionError. G-1 only json.loads the artifact. Named probes
enforce this teeth schema instead. Do not rebuild platform/schema (ADV circle).
"""
from __future__ import annotations

from typing import Any

import jsonschema

EXPECTED_IDS = ["P20", "P21", "P22", "P23", "P24", "P25"]

TEETH = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "title",
        "question",
        "answer",
        "family",
        "family_count",
        "library_status",
        "protocols",
        "tests",
        "negative_controls",
        "reviewer",
        "evidence",
        "min_bytes_threshold",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0041"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0041"},
        "family": {"const": "ANONYMOUS"},
        "family_count": {"const": 6},
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "answer": {"type": "string", "minLength": 40, "pattern": "UNSEAL"},
        "library_status": {
            "type": "object",
            "required": ["present", "count_status"],
            "properties": {
                "present": {"const": False},
                "count_status": {"type": "string", "minLength": 8},
            },
        },
        "protocols": {
            "type": "array",
            "minItems": 6,
            "maxItems": 6,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "slug",
                    "verdict",
                    "anonymity_lift_event",
                    "leaks_before_lift",
                ],
                "properties": {
                    "id": {"type": "string", "pattern": "^P2[0-5]$"},
                    "verdict": {"const": "EXECUTABLE"},
                    "anonymity_lift_event": {"const": "UNSEAL"},
                    "leaks_before_lift": {"type": "array", "minItems": 1},
                },
            },
        },
        "tests": {"type": "array", "minItems": 2},
        "negative_controls": {"type": "array", "minItems": 1},
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


def validator() -> jsonschema.Draft7Validator:
    jsonschema.Draft7Validator.check_schema(TEETH)
    return jsonschema.Draft7Validator(TEETH)


def iter_errors(doc: Any) -> list[str]:
    v = validator()
    errs = [f"{list(e.path)}: {e.message}" for e in v.iter_errors(doc)]
    if isinstance(doc, dict):
        ids = [
            str(p.get("id") or "")
            for p in (doc.get("protocols") or [])
            if isinstance(p, dict)
        ]
        if ids != EXPECTED_IDS:
            errs.append(f"protocol ids {ids} != {EXPECTED_IDS}")
    return errs


def rejects_garbage() -> bool:
    v = validator()
    garbage_docs = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0041", "state": "SUCCESS"},
        {"blob": "x" * 2000},
    )
    return all(list(v.iter_errors(g)) for g in garbage_docs)
