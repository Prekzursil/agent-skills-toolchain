#!/usr/bin/env python3
"""Disk-only $ref resolution for research-registry.schema.json.

jsonschema 4.10 RefResolver fetches https $ref by default. The catalog shim
points at ast-integrate.invalid, which is not a network host. This module
loads the physical schemas from disk and never opens a socket.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/research-registry.schema.json"
SCHEMA_STORE = (
    SHIM,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def artifact_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Merge report payload over the receipt so probes read one shape."""
    if not isinstance(doc, dict):
        return {}
    view = dict(doc)
    rpt = doc.get("report")
    if isinstance(rpt, dict):
        view.update(rpt)
    return view


def validator() -> Draft202012Validator:
    store: dict[str, dict] = {}
    for rel in SCHEMA_STORE:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    schema = json.loads((REPO / SHIM).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(
            schema.get("$id") or ("https://ast-integrate.invalid/" + SHIM)
        ),
        referrer=schema,
        store=store,
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors_of(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
