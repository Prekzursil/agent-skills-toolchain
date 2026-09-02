"""Offline contradiction-report validator for jsonschema 4.10.

The catalog shim $ref points at https://ast-integrate.invalid/... Draft7Validator
on this image follows that URL with requests and raises RefResolutionError.
Load the three on-disk schema files into a RefResolver store and refuse the
network. Domain payload lives under report once receipt_core is pinned.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/contradiction-report.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


class OfflineResolver(RefResolver):
    def resolve_remote(self, uri: str):  # noqa: ANN001
        raise RuntimeError(f"offline schema resolver refuses network fetch: {uri}")


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not isinstance(sid, str) or not sid:
            raise RuntimeError(f"schema missing $id: {rel}")
        store[sid] = doc
    return store


def validator() -> jsonschema.Draft7Validator:
    store = _store()
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = OfflineResolver(
        base_uri=str(schema["$id"]),
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def errors_of(instance: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
