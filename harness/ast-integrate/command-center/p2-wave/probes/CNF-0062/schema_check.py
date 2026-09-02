#!/usr/bin/env python3
"""Validate against citation-audit.schema.json using on-disk $ref targets.

Bare Draft7Validator follows https://ast-integrate.invalid/... over the network
and raises RefResolutionError. This store maps those $ids onto repo files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/citation-audit.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_store() -> dict[str, dict]:
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        rid = doc.get("$id")
        if isinstance(rid, str) and rid:
            store[rid] = doc
    return store


def validator() -> Draft7Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=load_store())
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def report_of(doc: dict) -> dict:
    r = doc.get("report")
    return r if isinstance(r, dict) else {}


def detector_of(doc: dict) -> dict:
    r = report_of(doc)
    d = r.get("detector")
    if isinstance(d, dict):
        return d
    ev = doc.get("evidence")
    return ev if isinstance(ev, dict) else {}


def citations_of(doc: dict) -> list[dict]:
    r = report_of(doc)
    rows = r.get("citations")
    if isinstance(rows, list):
        return [c for c in rows if isinstance(c, dict)]
    rows = doc.get("citations")
    if isinstance(rows, list):
        return [c for c in rows if isinstance(c, dict)]
    return []
