"""Disk-only validator for the catalog shim. Never fetches ast-integrate.invalid."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

from paths import REPO, SCHEMA_PATH, SCHEMA_REL

STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def schema_store() -> dict[str, dict]:
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        if not path.is_file():
            raise SystemExit(f"FAILED:CNF-0038 schema file missing {rel}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not isinstance(sid, str) or not sid:
            raise SystemExit(f"FAILED:CNF-0038 schema {rel} has no $id")
        store[sid] = doc
    return store


def validator():
    shim = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(shim, store=schema_store())
    return Draft202012Validator(shim, resolver=resolver)


def error_list(instance: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
