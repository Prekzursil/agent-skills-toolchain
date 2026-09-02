"""Offline catalog-schema validator for RES-0105. Never fetches HTTPS $id URLs."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, exceptions
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    store = {}
    for rel in (RECEIPT_REL, PROFILES_REL, SCHEMA_REL):
        data = _load(rel)
        ident = data.get("$id")
        if ident:
            store[ident] = data
    shim = _load(SCHEMA_REL)
    resolver = RefResolver.from_schema(shim, store=store)
    resolver.resolve_remote = lambda uri: (_ for _ in ()).throw(
        exceptions.RefResolutionError(f"offline: refused {uri}")
    )
    return Draft202012Validator(shim, resolver=resolver)
