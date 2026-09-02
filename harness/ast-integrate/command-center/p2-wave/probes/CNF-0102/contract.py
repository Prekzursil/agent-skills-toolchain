"""Disk-only schema validation and domain payload access for CNF-0102.

jsonschema 4.10 on this worker does not accept referencing.Registry (that API
landed in 4.18). Resolve ast-integrate.invalid $ref targets from the repo store
instead of the network.
"""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

from constants import REPO, SCHEMA_REL, UNIT_ID

BASE = "https://ast-integrate.invalid/"
_STORE_RELS = (
    "command-center/schema/bundle-audit.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Bundle-audit payload lives under report when the receipt is schema-valid."""
    report = doc.get("report")
    if isinstance(report, dict) and report.get("kind") == "bundle-audit":
        return report
    return doc


def _refuse_remote(uri: str):
    raise ValueError(f"refusing network schema retrieve: {uri}")


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in _STORE_RELS:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[BASE + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def validator():
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    ident = schema.get("$id") or (BASE + SCHEMA_REL)
    resolver = RefResolver(
        base_uri=ident,
        referrer=schema,
        store=_store(),
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return Draft202012Validator(schema, resolver=resolver)


def schema_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def schema_rejects_garbage() -> str | None:
    v = validator()
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": UNIT_ID, "blob": "x" * 2000},
    ):
        if not list(v.iter_errors(garbage)):
            return f"schema accepted garbage {list(garbage)[:2]}"
    return None
