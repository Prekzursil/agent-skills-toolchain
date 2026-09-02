#!/usr/bin/env python3
"""Disk-only Draft 2020-12 validator for the ARC-0098 catalog schema.

The declared shim $ref's https://ast-integrate.invalid/... which is not a
network host. jsonschema 4.10 on this box has no referencing.Registry kwarg,
so we bind those $id values to the files under the repo root.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SCHEMA_ID = (
    "https://ast-integrate.invalid/command-center/schema/"
    "conformance-report.schema.json"
)


def validator() -> Draft202012Validator:
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not isinstance(sid, str) or not sid:
            raise RuntimeError(f"schema missing $id: {rel}")
        store[sid] = doc
    schema = store[SCHEMA_ID]
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc):
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.absolute_path))


def control_runs_of(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    nested = report.get("control_runs")
    if isinstance(nested, dict) and nested:
        return nested
    top = doc.get("control_runs")
    return top if isinstance(top, dict) else {}
