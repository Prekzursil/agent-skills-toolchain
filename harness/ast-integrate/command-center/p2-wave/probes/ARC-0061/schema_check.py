"""Draft-07 subset checker for architecture-review.schema.json.

Avoids importing jsonschema (repo-root `platform/` shadows stdlib and
breaks uuid). Enforces required keys, enums, minItems, minLength, const.
Garbage objects must fail.

The catalog path command-center/schema/architecture-review.schema.json is a
generated $ref shim with no constraints of its own. This checker does not
resolve remote $id URLs, so a vacuous shim is replaced by LOCAL_REVIEW.
"""
from __future__ import annotations

from typing import Any

LOCAL_REVIEW: dict[str, Any] = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "claims",
        "evidence",
        "detector_control",
        "ordering_constraints",
        "reviewer",
        "answer",
    ],
    "properties": {
        "unit_id": {"type": "string", "const": "ARC-0061"},
        "state": {"type": "string", "enum": ["SUCCESS"]},
        "sentinel": {"type": "string", "minLength": 8},
        "answer": {"type": "string", "minLength": 32},
        "claims": {"type": "array", "minItems": 3},
        "evidence": {"type": "array", "minItems": 2},
        "ordering_constraints": {"type": "array", "minItems": 8},
        "detector_control": {
            "type": "object",
            "required": [
                "clean_duplicate_count",
                "planted_duplicate_count",
                "extraction_control_clean",
                "a9_design_present",
            ],
            "properties": {
                "clean_duplicate_count": {"type": "integer", "minimum": 0},
                "planted_duplicate_count": {"type": "integer", "minimum": 1},
                "extraction_control_clean": {"type": "boolean"},
                "a9_design_present": {"type": "boolean"},
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["independent", "scope_not_agreement", "added_failure_mode"],
            "properties": {
                "independent": {"type": "boolean"},
                "scope_not_agreement": {"type": "boolean"},
            },
        },
    },
}


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
    if isinstance(value, str) and "pattern" in schema:
        import re

        if re.search(schema["pattern"], value) is None:
            errs.append(f"{path}: pattern {schema['pattern']}")
    if isinstance(value, int) and "minimum" in schema:
        if value < int(schema["minimum"]):
            errs.append(f"{path}: minimum {schema['minimum']}")
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


def is_vacuous(schema: dict[str, Any]) -> bool:
    if schema.get("required") or schema.get("properties") or schema.get("type"):
        return False
    return True


def effective_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict) or is_vacuous(schema):
        return LOCAL_REVIEW
    return schema


def validate(doc: Any, schema: dict[str, Any]) -> list[str]:
    return _walk(doc, effective_schema(schema), "$")
