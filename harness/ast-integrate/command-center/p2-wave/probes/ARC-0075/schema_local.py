#!/usr/bin/env python3
"""Disk-only validator for the catalog decision-record schema.

jsonschema 4.10 on this host follows $ref to https://ast-integrate.invalid
and raises RefResolutionError (network). Map those $id URIs onto files
under the repo so empty garbage is a ValidationError and a live receipt
can actually pass.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/decision-record.schema.json"
_STORE_RELS = (
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
    SCHEMA_REL,
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft7Validator:
    shim = _load(SCHEMA_REL)
    store: dict[str, Any] = {}
    for rel in _STORE_RELS:
        doc = _load(rel)
        store["https://ast-integrate.invalid/" + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft7Validator(shim, resolver=resolver)


def errors(instance: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(instance):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)


def reject_empty_accept_live(doc: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Return (empty_rejected, live_accepted, live_errors)."""
    empty_errs = errors({})
    live_errs = errors(doc)
    return bool(empty_errs), not live_errs, live_errs


def validate_live(doc: dict[str, Any]) -> None:
    live_errs = errors(doc)
    if live_errs:
        raise ValidationError("live artifact schema-invalid: " + live_errs[0])
