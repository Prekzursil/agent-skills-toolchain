"""Offline validation of the catalog coordination-report shim (no network).

jsonschema 4.10 Draft7Validator follows $id/$ref via RefResolver and, without a
store, tries HTTPS to ast-integrate.invalid. Map those URIs onto repo files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/coordination-report.schema.json"
DISK_SCHEMAS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _retrieve(uri: str) -> dict[str, Any]:
    if not uri.startswith(BASE):
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing non-local schema uri (no network): {uri!r}"
        )
    rel = uri[len(BASE) :]
    target = (REPO / rel).resolve()
    root = REPO.resolve()
    if not str(target).startswith(str(root) + "/") or not target.is_file():
        raise jsonschema.exceptions.RefResolutionError(
            f"schema uri has no file on disk: {uri!r}"
        )
    return json.loads(target.read_text(encoding="utf-8"))


def schema_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in DISK_SCHEMAS:
        doc = _load(rel)
        store[BASE + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def load_schema() -> dict[str, Any]:
    return _load(SCHEMA_REL)


def validator(schema: dict[str, Any] | None = None) -> jsonschema.Draft7Validator:
    schema = schema if schema is not None else load_schema()
    resolver = jsonschema.RefResolver(
        base_uri=str(schema.get("$id") or BASE + SCHEMA_REL),
        referrer=schema,
        store=schema_store(),
        handlers={"https": _retrieve, "http": _retrieve},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def validate_or_raise(doc: dict[str, Any]) -> None:
    validator().validate(doc)


def payload_of(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report when the receipt_core forbids extras."""
    report = doc.get("report")
    return report if isinstance(report, dict) else doc
