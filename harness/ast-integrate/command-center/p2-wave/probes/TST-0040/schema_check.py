"""Disk-only jsonschema check for TST-0040 receipts.

jsonschema 4.10.3 on this host has no referencing.Registry keyword, so
platform/lib/schema_resolver.py cannot compile. Seed a local RefResolver
store from the catalog shim plus the two physical schema files it points at.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
REPORT_SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
SHIM = REPO / REPORT_SCHEMA_REL
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"


def _load(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not doc.get("$id"):
        raise RuntimeError(f"schema missing $id: {path}")
    return doc


@lru_cache(maxsize=1)
def validator() -> Draft202012Validator:
    shim = _load(SHIM)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver(
        base_uri=str(shim["$id"]), referrer=shim, store=store
    )
    return Draft202012Validator(shim, resolver=resolver)


def errors_for(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> bool:
    for blob in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "TST-0040", "state": "SUCCESS"},
        {"schema_version": 1, "unit_id": "TST-0040"},
    ):
        if not errors_for(blob):
            return False
    return True
