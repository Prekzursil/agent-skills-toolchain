"""Resolve interface-coverage $ref onto disk (jsonschema 4.10 RefResolver).

The shim at command-center/schema/interface-coverage.schema.json $ref's
https://ast-integrate.invalid/... which is not a network host. Fetching it
is a detector-failure (schema never actually constrains). This module maps
those $id values to the physical files under platform/schema/.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/interface-coverage.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> jsonschema.Draft7Validator:
    shim = _load(SHIM)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def payload(doc: dict) -> dict:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    rep = doc.get("report")
    return rep if isinstance(rep, dict) else doc
