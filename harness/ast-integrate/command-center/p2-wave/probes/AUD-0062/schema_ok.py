"""Disk-only validator for audit-metric-baseline receipts.

The catalog file is a generated $ref shim. jsonschema 4.10 on this host follows
https://ast-integrate.invalid and would fetch the network. Seed a RefResolver
store from on-disk schema files so garbage is a ValidationError and a live
receipt can pass. Does not rebuild platform/schema or ADV trees.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        doc = _load(rel)
        store["https://ast-integrate.invalid/" + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    shim = store["https://ast-integrate.invalid/" + SCHEMA_REL]
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL)),
        referrer=shim,
        store=store,
        cache_remote=False,
    )
    return Draft202012Validator(shim, resolver=resolver)


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:  # noqa: BLE001
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)


def garbage_is_rejected() -> bool:
    return bool(errors({"totally": "unrelated", "n": 999999})) and bool(errors({}))
