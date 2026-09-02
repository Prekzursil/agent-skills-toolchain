"""Offline Draft7 validation for the catalog $ref shim (jsonschema 4.10, no network)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "https://ast-integrate.invalid/"
STORE_RELS = (
    "command-center/schema/supply-chain-receipt.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _no_network(uri: str):  # pragma: no cover - fail-closed retrieve
    raise jsonschema.exceptions.RefResolutionError(
        f"refusing network schema retrieve: {uri}"
    )


def validator_for(schema_rel: str) -> jsonschema.Draft7Validator:
    schema = _load(schema_rel)
    store: dict[str, dict[str, Any]] = {}
    for rel in STORE_RELS:
        doc = _load(rel)
        posix = rel.replace("\\", "/")
        store[BASE + posix] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    resolver = jsonschema.RefResolver.from_schema(
        schema,
        store=store,
        handlers={"http": _no_network, "https": _no_network},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: Any, schema_rel: str) -> list[str]:
    out: list[str] = []
    for err in validator_for(schema_rel).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def validate(doc: Any, schema_rel: str) -> None:
    errors = iter_errors(doc, schema_rel)
    if errors:
        extra = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
        raise jsonschema.ValidationError(errors[0] + extra)


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Supply-chain payload lives under report; older top-level shape still works."""
    inner = doc.get("report")
    if isinstance(inner, dict) and inner.get("kind") == "supply-chain-receipt":
        return inner
    if isinstance(inner, dict) and inner.get("verification"):
        return inner
    return doc
