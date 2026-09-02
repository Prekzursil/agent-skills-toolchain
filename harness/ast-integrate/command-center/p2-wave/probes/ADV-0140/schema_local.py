"""Offline jsonschema for ADV-0140 gate-reachability receipts.

This host ships jsonschema 4.10.3 without `referencing`, so
platform/lib/schema_resolver.py cannot be imported. Resolve the catalog
shim $ref via RefResolver and a disk-only store. Network retrieve is refused.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/gate-reachability.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        data = _load(rel)
        store["https://ast-integrate.invalid/" + rel.replace("\\", "/")] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def validator():
    from jsonschema import Draft7Validator, RefResolver
    import jsonschema

    shim = _load(SCHEMA_REL)
    store = _disk_store()

    def retrieve(uri: str) -> dict[str, Any]:
        key = uri.split("#", 1)[0]
        if key in store:
            return store[key]
        if key.startswith("https://ast-integrate.invalid/"):
            rel = key[len("https://ast-integrate.invalid/") :]
            path = REPO / rel
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                store[key] = data
                return data
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing network retrieve for {uri!r}"
        )

    resolver = RefResolver(
        base_uri=str(shim.get("$id") or "https://ast-integrate.invalid/" + SCHEMA_REL),
        referrer=shim,
        store=store,
        handlers={"https": retrieve, "http": retrieve},
    )
    return Draft7Validator(shim, resolver=resolver)


def iter_errors(doc: object) -> list:
    return list(validator().iter_errors(doc))


def error_strings(doc: object) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
