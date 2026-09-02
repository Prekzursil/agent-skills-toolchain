"""Resolve catalog test-plan $ref onto disk (jsonschema 4.10, no network)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/test-plan.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> jsonschema.Draft7Validator:
    shim = load_json(SCHEMA_REL)
    profiles = load_json(PROFILES)
    receipt = load_json(RECEIPT)
    store = {
        shim.get("$id", ""): shim,
        profiles.get("$id", ""): profiles,
        receipt.get("$id", ""): receipt,
        "https://ast-integrate.invalid/" + PROFILES: profiles,
        "https://ast-integrate.invalid/" + RECEIPT: receipt,
        "https://ast-integrate.invalid/" + SCHEMA_REL: shim,
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or ""),
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def payload(doc: dict) -> dict:
    """Domain fields live in report (receipt_core additionalProperties=false)."""
    body = doc.get("report")
    if isinstance(body, dict):
        merged = dict(doc)
        merged.update(body)
        return merged
    return doc


def schema_errors(doc: dict) -> list[str]:
    v = validator()
    out = []
    for err in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out
