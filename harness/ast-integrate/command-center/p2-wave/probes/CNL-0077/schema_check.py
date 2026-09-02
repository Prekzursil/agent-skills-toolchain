#!/usr/bin/env python3
"""Validate CNL-0077 against the catalog council-design-note schema on disk.

jsonschema 4.10 on this worker has no `registry=` kwarg (that is 4.18+).
Refs are resolved from the on-disk $id store; nothing is fetched.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = REPO / "command-center/schema/council-design-note.schema.json"
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = _load(SHIM)
    store = {}
    for path in (SHIM, PROFILES, RECEIPT):
        doc = _load(path)
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or SHIM.as_uri()),
        referrer=shim,
        store=store,
    )
    return Draft202012Validator(shim, resolver=resolver)


def error_list(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
