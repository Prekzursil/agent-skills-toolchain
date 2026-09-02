#!/usr/bin/env python3
"""Offline jsonschema check for CNF-0130 (no remote $ref fetch).

jsonschema 4.10.3 follows https://ast-integrate.invalid over the network.
Seed a local RefResolver store from the shim plus the two physical files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_DECL = "command-center/schema/confirmation-tooling-receipt.schema.json"
SHIM = REPO / SCHEMA_DECL
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"


def _load(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not doc.get("$id"):
        raise RuntimeError(f"schema missing $id: {path}")
    return doc


def validator() -> Draft202012Validator:
    shim = _load(SHIM)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {shim["$id"]: shim, profiles["$id"]: profiles, receipt["$id"]: receipt}
    resolver = RefResolver(base_uri=str(shim["$id"]), referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def errors_for(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
