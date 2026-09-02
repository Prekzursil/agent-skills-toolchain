#!/usr/bin/env python3
"""Offline validator for command-center/schema/detector-control.schema.json.

jsonschema 4.10 Draft*Validator has no `registry=` kwarg (that is 4.18+), and a
bare Draft7Validator tries HTTPS to ast-integrate.invalid. Map $id onto disk.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
STORE_RELS = (
    "command-center/schema/detector-control.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
        path = REPO / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        uri = "https://ast-integrate.invalid/" + rel
        store[uri] = data
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = data
    return store


def validator():
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    store = _store()
    base = schema.get("$id") or "https://ast-integrate.invalid/" + SCHEMA_REL
    resolver = jsonschema.RefResolver(
        base_uri=str(base),
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: object) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def payload(doc: dict) -> dict:
    """Matrix fields live under report/extensions (receipt_core additionalProperties=false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}

    def pick(key, default=None):
        for src in (doc, report, ext):
            if isinstance(src, dict) and key in src and src[key] is not None:
                return src[key]
        return default

    return {
        "matrix": pick("matrix") or {},
        "accepted_repros": pick("accepted_repros") or [],
        "quarantined": pick("quarantined") or [],
        "detector_control": pick("detector_control") or {},
        "cnf0023_specificity": pick("cnf0023_specificity") or {},
    }
