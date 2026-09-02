#!/usr/bin/env python3
"""Load the CNF-0070 citation-audit schema used by emit and named probes.

The catalog path command-center/schema/citation-audit.schema.json is a generated
$ref shim. Draft7Validator against it raises RefResolutionError while retrieving
https://ast-integrate.invalid/... so this unit validates against the local file
that actually carries the verdict enum (was-true-then-changed vs never-supported).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
LOCAL = HERE / "citation-audit.schema.json"
CATALOG = (
    HERE.parents[3] / "command-center" / "schema" / "citation-audit.schema.json"
)


def schema() -> dict:
    return json.loads(LOCAL.read_text(encoding="utf-8"))


def catalog_has_verdict_enum() -> bool:
    if not CATALOG.is_file():
        return False
    try:
        doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    enum = (
        doc.get("properties", {})
        .get("citations", {})
        .get("items", {})
        .get("properties", {})
        .get("verdict", {})
        .get("enum")
        or []
    )
    return "was-true-then-changed" in enum and "never-supported" in enum


def validator() -> jsonschema.Draft7Validator:
    raw = (
        json.loads(CATALOG.read_text(encoding="utf-8"))
        if catalog_has_verdict_enum()
        else schema()
    )
    jsonschema.Draft7Validator.check_schema(raw)
    return jsonschema.Draft7Validator(raw)
