"""Validate against the test-receipt shim using on-disk $ref targets only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

SCHEMA_REL = "command-center/schema/test-receipt.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def make_validator(repo: Path) -> Draft202012Validator:
    store: dict[str, Any] = {}
    schema: dict[str, Any] | None = None
    for rel in STORE_RELS:
        doc = json.loads((repo / rel).read_text(encoding="utf-8"))
        uri = "https://ast-integrate.invalid/" + rel
        store[uri] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        if rel == SCHEMA_REL:
            schema = doc
    if schema is None:
        raise RuntimeError("test-receipt schema missing")
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL)),
        referrer=schema,
        store=store,
    )
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(repo: Path, instance: Any) -> list[Any]:
    return list(make_validator(repo).iter_errors(instance))
