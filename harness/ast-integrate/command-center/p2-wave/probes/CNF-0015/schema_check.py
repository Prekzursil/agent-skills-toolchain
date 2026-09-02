#!/usr/bin/env python3
"""Validate CNF-0015 receipts against the declared repro-report schema.

The command-center shim is a $ref into platform/schema. Bare jsonschema.validate
tries the network. This tree's jsonschema 4.10 takes RefResolver, not registry=.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/repro-report.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
]


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _retrieve(uri: str) -> dict:
    if uri.startswith(BASE):
        rel = uri[len(BASE) :].split("#", 1)[0]
        path = REPO / rel
        if path.is_file():
            return _load(rel)
    raise ValueError(f"non-local schema uri: {uri}")


def _aliases(rel: str, doc: dict) -> dict:
    store = {
        BASE + rel: doc,
        "file:///C:/Users/Prekzursil/source/ast-integrate/" + rel: doc,
        "file:///home/prekzursil/p2-g1/" + rel: doc,
    }
    ident = doc.get("$id")
    if isinstance(ident, str) and ident:
        store[ident] = doc
    return store


def _refuse(uri: str):
    raise ValueError(f"offline-refused {uri}")


def validator() -> Draft202012Validator:
    schema = _load(SCHEMA_REL)
    profiles = _load("platform/schema/artifact-class-profiles.schema.json")
    receipt = _load("platform/schema/receipt.schema.json")
    store = {}
    store.update(_aliases(SCHEMA_REL, schema))
    store.update(_aliases("platform/schema/artifact-class-profiles.schema.json", profiles))
    store.update(_aliases("platform/schema/receipt.schema.json", receipt))
    target = schema
    defs = profiles.get("$defs") if isinstance(profiles, dict) else None
    if isinstance(defs, dict) and isinstance(defs.get("repro-report"), dict):
        target = dict(defs["repro-report"])
        target["$defs"] = defs
    resolver = RefResolver(
        base_uri=BASE + SCHEMA_REL,
        referrer=schema,
        store=store,
        handlers={"https": _retrieve, "http": _refuse, "file": _refuse},
    )
    return Draft202012Validator(target, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def rejects_garbage() -> tuple[bool, list[str]]:
    notes: list[str] = []
    rejected = 0
    for i, g in enumerate(GARBAGE):
        errs = errors(g)
        if errs:
            rejected += 1
            notes.append(f"garbage[{i}] rejected:{errs[0][:80]}")
        else:
            notes.append(f"garbage[{i}] ACCEPTED")
    return rejected == len(GARBAGE), notes


def domain(doc: dict) -> dict:
    """Merge report payload over top-level keys (schema forbids extra top-level)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    merged = dict(doc)
    merged.update(ext)
    merged.update(report)
    return merged
