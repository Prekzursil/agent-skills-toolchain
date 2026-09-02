"""Offline research-registry validation for jsonschema 4.10.

The catalog shim $ref points at https://ast-integrate.invalid/... Draft*Validator
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
SCHEMA_REL = "command-center/schema/research-registry.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
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
        store["https://ast-integrate.invalid/" + rel.replace("\\", "/")] = doc
    return store


def validator() -> Draft202012Validator:
    store = _store()
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = OfflineResolver(
        base_uri=str(schema["$id"]),
        referrer=schema,
        store=store,
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors_of(instance: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> int:
    return sum(1 for g in GARBAGE if errors_of(g))
