"""Unwrap the detector payload and validate against the physical schema.

The catalog shim $ref uses https://ast-integrate.invalid URLs. Naive
jsonschema.validate tries the network. This worktree's jsonschema 4.10.3
has RefResolver, not the referencing.Registry API used by
platform/lib/schema_resolver.py, so validation here is disk-only via a
local store of those URIs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
BASE = "https://ast-integrate.invalid/"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def detector_spec(doc: dict[str, Any]) -> dict[str, Any]:
    """Receipt fields plus report payload (report wins on overlap)."""
    if not isinstance(doc, dict):
        return {}
    view = dict(doc)
    report = doc.get("report")
    if isinstance(report, dict):
        view.update(report)
    return view


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        store[BASE + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def schema_errors(doc: Any) -> list[str]:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=_store(),
    )
    validator = Draft202012Validator(schema, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
