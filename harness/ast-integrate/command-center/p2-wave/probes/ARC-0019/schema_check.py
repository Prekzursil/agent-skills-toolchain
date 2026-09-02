"""Draft-07 subset checker for ARC-0019.

The catalog architecture-review.schema.json is a generated $ref shim with
no local constraints. jsonschema against that file either cannot resolve
https://ast-integrate.invalid or accepts garbage. This walker enforces
the unit's own required shape so empty objects fail.
"""
from __future__ import annotations

from typing import Any


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _walk(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    errs: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _type_ok(value, expected_type):
        return [f"{path}: type {expected_type} got {type(value).__name__}"]

    if "const" in schema and value is not schema["const"] and value != schema["const"]:
        errs.append(f"{path}: const {schema['const']!r} got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: enum {schema['enum']} got {value!r}")
    if isinstance(value, str) and "minLength" in schema:
        if len(value) < int(schema["minLength"]):
            errs.append(f"{path}: minLength {schema['minLength']}")
    if isinstance(value, list) and "minItems" in schema:
        if len(value) < int(schema["minItems"]):
            errs.append(f"{path}: minItems {schema['minItems']}")

    if isinstance(value, dict):
        for key in schema.get("required") or []:
            if key not in value:
                errs.append(f"{path}.{key}: missing required")
        props = schema.get("properties") or {}
        for key, sub in props.items():
            if key in value:
                errs.extend(_walk(value[key], sub, f"{path}.{key}"))
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                errs.extend(_walk(item, item_schema, f"{path}[{i}]"))
    return errs


def validate(doc: Any, schema: dict[str, Any]) -> list[str]:
    return _walk(doc, schema, "$")


LOCAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "claims",
        "live_reconciliation",
        "reachability",
        "evidence",
        "reviewer",
        "author_failure_modes",
        "tests",
        "answer",
    ],
    "properties": {
        "unit_id": {"type": "string", "const": "ARC-0019"},
        "state": {"type": "string", "enum": ["SUCCESS", "PARTIAL"]},
        "sentinel": {"type": "string", "minLength": 8},
        "claims": {"type": "array", "minItems": 3},
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 2},
        "author_failure_modes": {"type": "array", "minItems": 5},
        "answer": {"type": "string", "minLength": 32},
    },
}
