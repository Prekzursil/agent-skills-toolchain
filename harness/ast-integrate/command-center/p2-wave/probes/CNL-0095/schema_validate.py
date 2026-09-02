"""Disk-only jsonschema validation for council-detector-spec (jsonschema 4.10).

The declared shim $ref points at https://ast-integrate.invalid/... which does
not resolve on the network. A bare jsonschema.validate therefore raises
RefResolutionError for every document, including garbage, and measures nothing.
This helper loads every on-disk *.schema.json by $id into a RefResolver store.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
]


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for root in (REPO / "command-center" / "schema", REPO / "platform"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.schema.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            sid = doc.get("$id") if isinstance(doc, dict) else None
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def resolver_for(schema: dict[str, Any] | None = None) -> jsonschema.RefResolver:
    schema = schema if schema is not None else load_schema()
    return jsonschema.RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=load_store(),
    )


def error_messages(instance: Any, schema: dict[str, Any] | None = None) -> list[str]:
    schema = schema if schema is not None else load_schema()
    resolver = resolver_for(schema)
    try:
        jsonschema.validate(instance, schema, resolver=resolver)
        return []
    except jsonschema.ValidationError as exc:
        loc = "/".join(str(p) for p in exc.absolute_path) or "<root>"
        return [f"{loc}: {exc.message}"]
    except jsonschema.RefResolutionError as exc:
        return [f"ref-unresolved: {exc}"]


def garbage_rejected() -> int:
    schema = load_schema()
    n = 0
    for g in GARBAGE:
        if error_messages(g, schema):
            n += 1
    return n


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Council-detector payload lives under report (receipt_core forbids extras)."""
    report = doc.get("report")
    if isinstance(report, dict) and report.get("kind") == "council-detector-spec":
        return report
    if isinstance(report, dict) and report:
        return report
    return doc
