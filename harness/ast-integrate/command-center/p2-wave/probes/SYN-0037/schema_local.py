"""Offline jsonschema for SYN-0037 independence-audit receipts.

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
SCHEMA_REL = "command-center/schema/independence-audit.schema.json"
BASE = "https://ast-integrate.invalid/"
DISK_SCHEMAS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in DISK_SCHEMAS:
        data = _load(rel)
        store[BASE + rel.replace("\\", "/")] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def errors_for(doc: object) -> list[str]:
    import jsonschema
    from jsonschema import Draft7Validator, RefResolver

    shim = _load(SCHEMA_REL)
    store = _disk_store()

    def retrieve(uri: str) -> dict[str, Any]:
        key = uri.split("#", 1)[0]
        if key in store:
            return store[key]
        if key.startswith(BASE):
            rel = key[len(BASE) :]
            path = REPO / rel
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                store[key] = data
                return data
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing network retrieve for {uri!r}"
        )

    resolver = RefResolver(
        base_uri=str(shim.get("$id") or BASE + SCHEMA_REL),
        referrer=shim,
        store=store,
        handlers={"https": retrieve, "http": retrieve},
    )
    validator = Draft7Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
