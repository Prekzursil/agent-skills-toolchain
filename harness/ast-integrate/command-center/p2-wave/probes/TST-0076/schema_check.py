#!/usr/bin/env python3
"""Offline jsonschema $ref resolution for TST-0076 (no network).

command-center/schema/detector-control.schema.json is a generated shim whose
$ref is https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json
#/$defs/detector-control. jsonschema 4.10 RefResolver tries that host and
raises RefResolutionError, which is not a ValidationError, so a naive
Draft7Validator(shim) neither accepts the receipt nor rejects garbage.

This module loads the physical schemas from disk into a RefResolver store.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver, ValidationError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
_FILES = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in _FILES:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    return store


def validator() -> Draft202012Validator:
    schema = load_schema()
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or SCHEMA_REL),
        referrer=schema,
        store=load_store(),
    )
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def validate(doc: Any) -> None:
    validator().validate(doc)


def garbage_rejected(sample: Any | None = None) -> bool:
    if sample is None:
        sample = {"totally": "unrelated", "passing_tests": 999999}
    try:
        validate(sample)
    except ValidationError:
        return True
    return False
