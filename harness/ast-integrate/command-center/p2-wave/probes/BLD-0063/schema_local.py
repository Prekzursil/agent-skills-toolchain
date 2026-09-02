"""Validate coverage-matrix receipts against on-disk schemas (no network)."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
SHIM = "command-center/schema/coverage-matrix.schema.json"
STORE_RELS = (
    SHIM,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _store() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            out[ident] = doc
    return out


def validator() -> Draft7Validator:
    shim = json.loads((REPO / SHIM).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(shim, store=_store())
    return Draft7Validator(shim, resolver=resolver)


def iter_errors(doc: object) -> list[str]:
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator().iter_errors(doc)
    ]


def garbage_rejected() -> bool:
    probes = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "BLD-0063", "state": "SUCCESS"},
    ]
    return all(bool(iter_errors(p)) for p in probes)
