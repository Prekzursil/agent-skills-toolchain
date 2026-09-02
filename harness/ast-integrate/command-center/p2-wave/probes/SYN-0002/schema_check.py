"""Disk-local catalog-schema checks for SYN-0002.

The catalog shim at command-center/schema/detector-control.schema.json is a
$ref into platform/schema/. Draft7Validator would fetch
https://ast-integrate.invalid/ over the network. This module loads those
targets from disk into a RefResolver store (jsonschema 4.10 on this box
does not accept the referencing Registry kwarg used by
platform/lib/schema_resolver.py).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA = "command-center/schema/detector-control.schema.json"
SCHEMA_FILES = (
    "command-center/schema/detector-control.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated"},
    {"blob": "x" * 2000},
    {"unit_id": "nope"},
    {"unit_id": "SYN-0002", "state": "SUCCESS"},
)


@lru_cache(maxsize=1)
def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in SCHEMA_FILES:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or "").strip()
        if not sid:
            raise RuntimeError(f"schema missing $id: {rel}")
        store[sid] = doc
    return store


def validator():
    schema = _store()[
        json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))["$id"]
    ]
    resolver = RefResolver(
        base_uri=schema["$id"],
        referrer=schema,
        store=_store(),
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors_for(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def rejects_garbage() -> bool:
    for item in GARBAGE:
        if not errors_for(item):
            return False
    return True
