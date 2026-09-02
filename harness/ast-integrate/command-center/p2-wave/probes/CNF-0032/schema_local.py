#!/usr/bin/env python3
"""Disk-only jsonschema resolver for causality-report (no network)."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/causality-report.schema.json"
BASE = "https://ast-integrate.invalid/"
PINNED = (
    "command-center/schema/causality-report.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _no_remote(uri: str):
    raise RefResolutionError(f"refusing network schema fetch: {uri}")


def load_store() -> dict:
    store: dict = {}
    for rel in PINNED:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or (BASE + rel))
        store[sid] = doc
        store[BASE + rel] = doc
    return store


def validator():
    store = load_store()
    schema = store[BASE + SCHEMA_REL]
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=store,
        handlers={"https": _no_remote, "http": _no_remote},
    )
    return Draft202012Validator(schema, resolver=resolver)


def error_messages(doc: dict) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<resolver>: {exc}")
    return sorted(out)
