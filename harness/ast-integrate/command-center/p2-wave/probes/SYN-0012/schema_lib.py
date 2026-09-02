#!/usr/bin/env python3
"""Validate SYN-0012 against the catalog output_schema (resolved, no network)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/sensitivity-report.schema.json"
SHIM_ID = (
    "https://ast-integrate.invalid/command-center/schema/sensitivity-report.schema.json"
)
PROFILES_ID = (
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json"
)
RECEIPT_ID = "https://ast-integrate.invalid/platform/schema/receipt.schema.json"


def catalog_validator():
    """Draft-2020-12 validator with a local $ref store. Never hits the network."""
    shim = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        SHIM_ID: shim,
        PROFILES_ID: profiles,
        RECEIPT_ID: receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=SHIM_ID,
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def schema_errors(doc: Any) -> list[str]:
    validator = catalog_validator()
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
