"""Disk-only validator for command-center/schema/failing-test-receipt.schema.json.

The catalog shim $ref's https://ast-integrate.invalid/... . jsonschema 4.10
follows that URL and raises RefResolutionError (or tries the network). Seed a
RefResolver store from on-disk schema files. Does not rebuild platform/schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/failing-test-receipt.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def schema_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for meta in (Draft202012Validator.META_SCHEMA, Draft7Validator.META_SCHEMA):
        seeded = RefResolver.from_schema(meta)
        for uri, doc in seeded.store.items():
            store.setdefault(str(uri), doc)
    for rel in STORE_RELS:
        doc = _load(rel)
        store["https://ast-integrate.invalid/" + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def validator() -> Draft202012Validator:
    shim = _load(SCHEMA_REL)
    resolver = RefResolver(
        base_uri=str(
            shim.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL)
        ),
        referrer=shim,
        store=schema_store(),
        cache_remote=False,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return Draft202012Validator(shim, resolver=resolver)


def _fmt(err: Any) -> str:
    loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{loc}: {err.message}"


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            out.append(_fmt(err))
    except Exception as exc:  # noqa: BLE001
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)
