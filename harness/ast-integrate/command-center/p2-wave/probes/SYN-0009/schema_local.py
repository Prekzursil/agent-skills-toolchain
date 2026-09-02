"""Disk-only validator for command-center/schema/synthesis-candidate.schema.json.

jsonschema 4.10 Draft7Validator follows the catalog shim $ref over HTTPS to
ast-integrate.invalid and raises. This store maps those $ids onto repo files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/synthesis-candidate.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def load_store() -> dict[str, dict]:
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        rid = doc.get("$id")
        if isinstance(rid, str) and rid:
            store[rid] = doc
    return store


def validator() -> Draft7Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=load_store())
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> bool:
    for g in GARBAGE:
        if not iter_errors(g):
            return False
    return True


def payload(doc: dict) -> dict:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and report:
        return report
    ext = doc.get("extensions")
    if isinstance(ext, dict) and ext:
        return ext
    return doc
