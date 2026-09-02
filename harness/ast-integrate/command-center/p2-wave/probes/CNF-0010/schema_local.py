"""Offline jsonschema 4.10 validator for the catalog environment-manifest shim.

jsonschema 4.10.3 on this host follows $ref over HTTPS. The catalog shim's
$id lives at https://ast-integrate.invalid/... which does not resolve on the
network. This module loads the shim plus the two physical schema files into
a RefResolver store so validation stays on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/environment-manifest.schema.json"
PHYSICAL = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_store() -> dict[str, dict]:
    store: dict[str, dict] = {}
    for rel in PHYSICAL:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise RuntimeError(f"schema {rel} is not an object")
        sid = str(doc.get("$id") or (BASE + rel.replace("\\", "/")))
        store[sid] = doc
        store[BASE + rel.replace("\\", "/")] = doc
        store[path.resolve().as_uri()] = doc
    return store


def make_validator() -> Draft7Validator:
    path = REPO / SCHEMA_REL
    schema = json.loads(path.read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=load_store(),
    )
    return Draft7Validator(schema, resolver=resolver)


def schema_errors(instance: Any, validator: Draft7Validator | None = None) -> list[str]:
    v = validator or make_validator()
    out: list[str] = []
    for err in v.iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def payload(doc: dict) -> dict:
    """Domain fields live on report when the receipt_core shell is present."""
    rep = doc.get("report")
    if isinstance(rep, dict) and rep.get("kind") == "environment-manifest":
        return rep
    return doc
