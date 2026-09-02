"""Offline jsonschema 4.10 validator for the catalog compatibility-matrix shim.

Does not fetch ast-integrate.invalid. Draft7 + RefResolver store only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/compatibility-matrix.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"

INTERSECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["computed", "members", "cardinality"],
    "properties": {
        "computed": {"type": "boolean"},
        "members": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "cardinality": {"type": "integer", "minimum": 0},
    },
}


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def store() -> dict:
    shim = _load(SCHEMA_REL)
    profiles = _load(PROFILES_REL)
    receipt = _load(RECEIPT_REL)
    out = {
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/command-center/schema/compatibility-matrix.schema.json": shim,
    }
    for doc in (shim, profiles, receipt):
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            out[ident] = doc
    return out


def validator(schema: dict | None = None):
    import jsonschema

    shim = _load(SCHEMA_REL)
    target = schema if schema is not None else shim
    resolver = jsonschema.RefResolver.from_schema(target, store=store())
    return jsonschema.Draft7Validator(target, resolver=resolver)


def errors(instance: Any, schema: dict | None = None) -> list[str]:
    out = []
    for err in validator(schema).iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def bound_intersection_schema() -> dict:
    """Draft-07 ignores keywords sibling to $ref, so wrap with allOf."""
    return {
        "allOf": [
            _load(SCHEMA_REL),
            {
                "type": "object",
                "required": ["report"],
                "properties": {
                    "report": {
                        "type": "object",
                        "required": ["intersection"],
                        "properties": {"intersection": INTERSECTION_SCHEMA},
                    }
                },
            },
        ]
    }
