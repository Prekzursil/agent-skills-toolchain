#!/usr/bin/env python3
"""Disk-only validator for the catalog council-design-note shim.

jsonschema 4.10 RefResolver otherwise GETs https://ast-integrate.invalid/
and raises RefResolutionError. This module maps those $ids onto files
already in the repo. It does not rewrite command-center/schema/ (no ADV
rebuild circle).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/council-design-note.schema.json"
_RELATIVE = (
    "command-center/schema/council-design-note.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _store() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    store: dict[str, dict[str, Any]] = {}
    shim: dict[str, Any] | None = None
    for rel in _RELATIVE:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if not isinstance(ident, str) or not ident:
            raise SystemExit(f"FAILED:CNL-0027 schema {rel} missing $id")
        store[ident] = doc
        if rel == DECLARED:
            shim = doc
    if shim is None:
        raise SystemExit("FAILED:CNL-0027 catalog shim not loaded")
    return shim, store


def validator() -> Draft202012Validator:
    shim, store = _store()
    resolver = RefResolver(base_uri=shim["$id"], referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def error_messages(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def fixture_scores(doc: dict[str, Any]) -> dict[str, Any]:
    """Scores live under report (receipt_core additionalProperties is false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    scores = report.get("fixture_scores") if isinstance(report, dict) else None
    if isinstance(scores, dict) and scores:
        return scores
    top = doc.get("fixture_scores")
    return top if isinstance(top, dict) else {}
