#!/usr/bin/env python3
"""Validate CNF-0114 receipts against security-report.schema.json.

The command-center shim is a $ref into platform/schema. Bare jsonschema.validate
tries the network. This tree's jsonschema 4.10 takes RefResolver, not registry=.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/security-report.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "CNF-0114", "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0114"},
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


def validator() -> Draft202012Validator:
    schema = _load(SCHEMA_REL)
    store = {
        BASE + SCHEMA_REL: schema,
        BASE + "platform/schema/artifact-class-profiles.schema.json": _load(
            "platform/schema/artifact-class-profiles.schema.json"
        ),
        BASE + "platform/schema/receipt.schema.json": _load(
            "platform/schema/receipt.schema.json"
        ),
    }
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=store,
        handlers={"https": _retrieve},
    )
    return Draft202012Validator(schema, resolver=resolver)


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
