"""Resolve compatibility-matrix $ref onto disk (jsonschema 4.10 RefResolver).

The catalog shim at command-center/schema/compatibility-matrix.schema.json
$ref's https://ast-integrate.invalid/... which is not a network host. A bare
Draft7Validator follows that $ref over HTTPS and either hangs or raises
RefResolutionError, so the schema never actually constrains. This module maps
those $id values to the physical files under platform/schema/.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/compatibility-matrix.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator():
    shim = _load(SHIM)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {
        str(shim.get("$id")): shim,
        str(profiles.get("$id")): profiles,
        str(receipt.get("$id")): receipt,
        "https://ast-integrate.invalid/command-center/schema/compatibility-matrix.schema.json": shim,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
