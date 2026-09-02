"""Disk-only JSON Schema resolver for the catalog test-plan shim.

This worktree's jsonschema is 4.10.x (RefResolver, no referencing).
platform/lib/schema_resolver.py needs jsonschema>=4.18. We load the
physical $id documents from disk and never hit the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

SCHEMA_REL = "command-center/schema/test-plan.schema.json"
STORE_RELS = (
    "command-center/schema/test-plan.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_store(repo: Path) -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        doc = json.loads((repo / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator_for(repo: Path, schema_rel: str = SCHEMA_REL) -> Draft7Validator:
    schema = json.loads((repo / schema_rel).read_text(encoding="utf-8"))
    store = load_store(repo)
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(repo: Path, instance: Any, schema_rel: str = SCHEMA_REL) -> list[str]:
    v = validator_for(repo, schema_rel)
    out: list[str] = []
    for err in v.iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
