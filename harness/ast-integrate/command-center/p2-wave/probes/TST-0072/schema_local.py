#!/usr/bin/env python3
"""Validate TST-0072 against the catalog test-receipt shim with no network.

jsonschema 4.10 follows $id/$ref over HTTPS. The catalog shim points at
https://ast-integrate.invalid/... which is not a host. Load the physical
files from disk into a RefResolver store so garbage is rejected.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/test-receipt.schema.json"
BASE_URI = "https://ast-integrate.invalid/"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[BASE_URI + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def _https_handler(uri: str) -> dict[str, Any]:
    if not uri.startswith(BASE_URI):
        raise ValueError(f"refusing non-local schema uri: {uri}")
    rel = uri[len(BASE_URI) :].split("#", 1)[0]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise ValueError(f"schema uri missing on disk: {uri}")
    return json.loads(path.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    schema = load_schema()
    resolver = RefResolver(
        base_uri=schema.get("$id") or (BASE_URI + SCHEMA_REL),
        referrer=schema,
        store=_store(),
        handlers={"https": _https_handler},
    )
    return Draft202012Validator(schema, resolver=resolver)


def iter_error_strings(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_accepted() -> object | None:
    v = validator()
    for garbage in (
        {},
        {"unit_id": "TST-0072", "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if v.is_valid(garbage):
            return garbage
    return None
