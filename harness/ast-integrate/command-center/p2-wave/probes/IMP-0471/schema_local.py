"""Disk-local jsonschema resolver for the mutation-report catalog shim."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/mutation-report.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        store[f"https://ast-integrate.invalid/{rel}"] = doc
    return store


def validator() -> Draft7Validator:
    schema = load_schema()
    resolver = RefResolver.from_schema(schema, store=load_store())
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: object) -> list:
    return list(validator().iter_errors(doc))
