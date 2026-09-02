"""Disk-only schema validation for SYN-0015.

Catalog output_schema is a generated $ref shim. jsonschema 4.10 follows
https://ast-integrate.invalid over the network (RefResolutionError), which is
not a ValidationError. Even after a disk store is attached, the physical
overclaim-scan profile is generic_report and does not constrain
flagged_sentences.corrected_sentence. Bound schema is the unit discriminator
for empty rewrite / garbage; catalog schema is still required (parses against
output_schema).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/overclaim-scan.schema.json"
BOUND_SCHEMA = "command-center/p2-wave/probes/SYN-0015/bound.schema.json"
PINNED = (
    CATALOG_SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
BASE = "https://ast-integrate.invalid/"


def _no_remote(uri: str) -> None:
    raise RefResolutionError(f"refusing network schema fetch: {uri}")


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def catalog_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PINNED:
        doc = _load(rel)
        store[BASE + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def catalog_validator() -> Draft202012Validator:
    store = catalog_store()
    schema = store[BASE + CATALOG_SCHEMA]
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + CATALOG_SCHEMA)),
        referrer=schema,
        store=store,
        handlers={"https": _no_remote, "http": _no_remote},
    )
    return Draft202012Validator(schema, resolver=resolver)


def bound_validator() -> Draft7Validator:
    schema = _load(BOUND_SCHEMA)
    return Draft7Validator(schema)


def _messages(validator: Any, doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator.iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<resolver>: {exc}")
    return sorted(out)


def catalog_errors(doc: Any) -> list[str]:
    return _messages(catalog_validator(), doc)


def bound_errors(doc: Any) -> list[str]:
    return _messages(bound_validator(), doc)
