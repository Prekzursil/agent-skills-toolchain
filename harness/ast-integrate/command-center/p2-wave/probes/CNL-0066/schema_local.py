#!/usr/bin/env python3
"""Disk-only validator for council-design-note (no circular receipt $ref).

The catalog shim $ref's artifact-class-profiles allOf receipt_core, which
RecursionError's jsonschema 4.x RefResolver. This local schema still rejects
empty/garbage objects and a dropped answer/evidence field.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator, ValidationError

__all__ = ["ValidationError", "validate_artifact", "validator"]

LOCAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["unit_id", "state", "answer", "evidence"],
    "additionalProperties": True,
    "properties": {
        "unit_id": {"type": "string", "const": "CNL-0066"},
        "state": {"type": "string", "minLength": 1},
        "answer": {"type": "string", "minLength": 20},
        "evidence": {
            "type": "array",
            "minItems": 2,
            "items": {"type": "object"},
        },
        "negative_controls": {"type": "array", "minItems": 1},
        "records": {"type": "array", "minItems": 1},
    },
}


def validator() -> Draft202012Validator:
    return Draft202012Validator(LOCAL_SCHEMA)


def validate_artifact(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
