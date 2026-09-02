"""Offline council-detector-spec validation for jsonschema 4.10.

The catalog shim $ref points at https://ast-integrate.invalid/... Draft7Validator
on this image follows that URL with requests and crashes. This module loads the
three on-disk schema files into a RefResolver store and refuses the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
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


def validator() -> Draft202012Validator:
    store = _store()
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    resolver = OfflineResolver(
        base_uri=str(schema["$id"]),
        referrer=schema,
        store=store,
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors_of(instance: Any) -> list[str]:
    if not isinstance(instance, dict) or "unit_id" not in instance:
        return ["<root>: missing unit_id (not a council-detector-spec)"]
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Council payload lives under report once the receipt_core pin is on."""
    rep = doc.get("report")
    if isinstance(rep, dict) and "kind" in rep:
        return rep
    return doc
