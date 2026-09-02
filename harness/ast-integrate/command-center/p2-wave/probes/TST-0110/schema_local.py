#!/usr/bin/env python3
"""Disk-only jsonschema resolver for the benchmark-receipt shim.

jsonschema 4.10 on this host follows https://ast-integrate.invalid/ over the
network and raises RefResolutionError. Map the three on-disk schemas by $id.
Do not rebuild the ADV schema substrate.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/benchmark-receipt.schema.json"
_STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "TST-0110", "state": "SUCCESS"},
)


def validator() -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    shim = None
    for rel in _STORE_RELS:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = data.get("$id")
        if not isinstance(ident, str) or not ident:
            raise RuntimeError(f"schema {rel} has no $id")
        store[ident] = data
        if rel == SCHEMA_REL:
            shim = data
    if shim is None:
        raise RuntimeError("benchmark-receipt shim missing")
    resolver = jsonschema.RefResolver(
        base_uri=str(shim["$id"]),
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def error_messages(doc: object) -> list[str]:
    if not isinstance(doc, dict) or "unit_id" not in doc or "report" not in doc:
        return ["<root>: missing unit_id/report (not a benchmark-receipt)"]
    msgs: list[str] = []
    for err in sorted(validator().iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        msgs.append(f"{loc}: {err.message}")
    return msgs


def rejects_garbage() -> bool:
    return all(bool(error_messages(item)) for item in GARBAGE)
