#!/usr/bin/env python3
"""Validate CNF-0078 artifacts against output_schema using on-disk $ref only.

This tree's jsonschema is 4.10.3 (RefResolver API). platform/lib/schema_resolver.py
needs jsonschema>=4.18 (`registry=`). Probes must still fail closed on an invalid
document and reject garbage, so this module wires the same physical $ref chain
through RefResolver with a disk store. No network.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA = "command-center/schema/similarity-report.schema.json"
BASE = "https://ast-integrate.invalid/"
_PHYSICAL = (
    "command-center/schema/similarity-report.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _store() -> dict:
    store: dict[str, dict] = {}
    for rel in _PHYSICAL:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store[BASE + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def errors(doc: object) -> list[str]:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA)),
        referrer=schema,
        store=_store(),
    )
    validator = Draft202012Validator(schema, resolver=resolver)
    out: list[str] = []
    try:
        for err in validator.iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        return [f"<ref>: {exc}"]
    return sorted(out)
