"""Offline jsonschema resolver for the catalog regression-delta shim.

jsonschema 4.10 follows https://ast-integrate.invalid $ref over the network.
This store maps those $id values onto platform/schema files on disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/regression-delta.schema.json"
PHYSICAL = (
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
    SCHEMA_REL,
)


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PHYSICAL:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store[path.resolve().as_uri()] = doc
        store[rel] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
            store[sid.split("#")[0]] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    return store


def validator() -> Draft202012Validator:
    schema_path = REPO / SCHEMA_REL
    referrer = json.loads(schema_path.read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(referrer.get("$id") or schema_path.resolve().as_uri()),
        referrer=referrer,
        store=_store(),
    )
    return Draft202012Validator(referrer, resolver=resolver)


def schema_errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    return report if isinstance(report, dict) else doc
