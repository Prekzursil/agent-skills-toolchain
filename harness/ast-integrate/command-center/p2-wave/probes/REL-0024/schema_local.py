"""Offline validator for command-center/schema/regression-seed-receipt.schema.json.

Distro jsonschema 4.10 follows $ref over HTTPS to ast-integrate.invalid.
Map those URIs onto the files on this worktree so a real receipt_core
document validates and garbage is rejected, with no network.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import RefResolver
from jsonschema.validators import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/regression-seed-receipt.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[f"https://ast-integrate.invalid/{rel}"] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def validator() -> Draft202012Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=_store())
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: object) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))
