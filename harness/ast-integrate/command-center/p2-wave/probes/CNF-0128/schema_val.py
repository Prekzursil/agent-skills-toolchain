#!/usr/bin/env python3
"""Offline validation of the phase-gate-report shim (no network).

This box ships jsonschema 4.10, which still uses RefResolver and would
otherwise fetch https://ast-integrate.invalid/. The store maps those $ids
onto the files that already exist in this repo.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/phase-gate-report.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"


def load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = load(SCHEMA_REL)
    profiles = load(PROFILES_REL)
    receipt = load(RECEIPT_REL)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver(base_uri=shim["$id"], referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def errors(doc) -> list[str]:
    if not isinstance(doc, dict) or "unit_id" not in doc or "report" not in doc:
        return ["<root>: missing unit_id/report (not a phase-gate-report)"]
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
