"""Offline validator for the catalog conformance-report shim.

Debian jsonschema 4.10 cannot take referencing.Registry. Preload the
ast-integrate.invalid $id documents from disk so $ref never hits the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

from paths import REPO, SCHEMA_REL

_STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def make_validator() -> Draft202012Validator:
    store: dict[str, Any] = {}
    for rel in _STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel.replace("\\", "/")] = doc
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def validate_doc(doc: dict[str, Any]) -> list[str]:
    validator = make_validator()
    errs = [
        f"{list(e.absolute_path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    ]
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            errs.append("schema accepted garbage")
            break
    return errs


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain rows live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("steps"), list):
        return report
    ext = doc.get("extensions")
    if isinstance(ext, dict) and isinstance(ext.get("steps"), list):
        return ext
    return doc
