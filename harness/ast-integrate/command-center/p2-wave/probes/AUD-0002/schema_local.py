#!/usr/bin/env python3
"""Disk-only jsonschema resolver for audit-inventory (no network).

Debian jsonschema 4.10 cannot take referencing.Registry. Preload the
ast-integrate.invalid $id documents from disk so $ref never hits HTTP.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
BASE = "https://ast-integrate.invalid/"
PINNED = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)


def _no_remote(uri: str):
    raise RefResolutionError(f"refusing network schema fetch: {uri}")


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PINNED:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or (BASE + rel.replace("\\", "/")))
        store[sid] = doc
        store[BASE + rel.replace("\\", "/")] = doc
    return store


def make_validator() -> Draft202012Validator:
    store = load_store()
    schema = store[BASE + SCHEMA_REL.replace("\\", "/")]
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
        validator = make_validator()
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<resolver>: {exc}")
    return out


def garbage_rejected() -> int:
    validator = make_validator()
    rejected = 0
    for blob in GARBAGE:
        try:
            if list(validator.iter_errors(blob)):
                rejected += 1
        except RefResolutionError:
            rejected += 1
    return rejected
