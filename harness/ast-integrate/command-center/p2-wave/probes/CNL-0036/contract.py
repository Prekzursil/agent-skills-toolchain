"""Shared loaders for CNL-0036 probes: sweep block + catalog-schema errors.

This tree's jsonschema is 4.10.3 (RefResolver). platform/lib/schema_resolver.py
needs jsonschema>=4.18 (`registry=`). Draft7Validator on the catalog shim
fetches https://ast-integrate.invalid/. Both of those fingerprints failed;
this module wires the same physical $ref chain through a disk-only store.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
_RELATIVE = (
    "command-center/schema/council-design-note.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def sweep_of(doc: dict) -> dict:
    """Find the permutation-sweep table on a receipt or a legacy note."""
    rec = doc.get("sweep")
    if isinstance(rec, dict) and rec.get("cyclic4"):
        return rec
    report = doc.get("report")
    if isinstance(report, dict):
        rec = report.get("sweep")
        if isinstance(rec, dict) and rec.get("cyclic4"):
            return rec
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        rec = ext.get("sweep")
        if isinstance(rec, dict) and rec.get("cyclic4"):
            return rec
    return {}


def _store() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    store: dict[str, dict[str, Any]] = {}
    shim: dict[str, Any] | None = None
    for rel in _RELATIVE:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if not isinstance(ident, str) or not ident:
            raise SystemExit(f"FAILED:CNL-0036 schema {rel} missing $id")
        store[ident] = doc
        if rel == SCHEMA_REL:
            shim = doc
    if shim is None:
        raise SystemExit("FAILED:CNL-0036 catalog shim not loaded")
    return shim, store


def validator() -> Draft202012Validator:
    shim, store = _store()
    resolver = RefResolver(base_uri=shim["$id"], referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def schema_errors(doc: Any) -> list[str]:
    """Validate against the catalog output_schema. Empty list means valid."""
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        return [f"<ref>: {exc}"]
    return sorted(out)
