"""Validate CNF-0155 against the catalog shim (disk-resolved) plus the unit overlay.

The catalog file command-center/schema/discrepancy-ledger.schema.json is a generated
$ref shim. jsonschema 4.10 would otherwise fetch https://ast-integrate.invalid over
the network. This module loads the physical schemas from disk into a RefResolver
store. The shim does not constrain tiebreak_test_id; overlay.schema.json does.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/discrepancy-ledger.schema.json"
OVERLAY_REL = "command-center/p2-wave/probes/CNF-0155/overlay.schema.json"
PHYSICAL = (
    "command-center/schema/discrepancy-ledger.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def catalog_validator() -> Draft202012Validator:
    store: dict[str, dict] = {}
    for rel in PHYSICAL:
        doc = _load(rel)
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    shim = store[
        "https://ast-integrate.invalid/command-center/schema/discrepancy-ledger.schema.json"
    ]
    resolver = RefResolver(
        base_uri=shim["$id"] + "#",
        referrer=shim,
        store=store,
    )
    return Draft202012Validator(shim, resolver=resolver)


def overlay_validator() -> Draft202012Validator:
    overlay = _load(OVERLAY_REL)
    return Draft202012Validator(overlay)


def error_list(validator: Draft202012Validator, doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def catalog_errors(doc: Any) -> list[str]:
    return error_list(catalog_validator(), doc)


def overlay_errors(doc: Any) -> list[str]:
    return error_list(overlay_validator(), doc)


def validate_receipt(doc: Any) -> list[str]:
    return catalog_errors(doc) + overlay_errors(doc)


def report_view(doc: dict) -> dict:
    """Domain payload lives under report (receipt_core additionalProperties=false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return {
        "adjudications": list(report.get("adjudications") or doc.get("adjudications") or []),
        "fingerprint": list(report.get("fingerprint") or doc.get("fingerprint") or []),
        "live_corpus": dict(report.get("live_corpus") or doc.get("live_corpus") or {}),
        "per_vendor_error_profile": dict(
            report.get("per_vendor_error_profile")
            or doc.get("per_vendor_error_profile")
            or {}
        ),
        "controls": dict(report.get("controls") or doc.get("controls") or {}),
        "taxonomy": list(report.get("taxonomy") or doc.get("taxonomy") or []),
    }


def adjudications_parent(doc: dict) -> dict:
    report = doc.get("report")
    if isinstance(report, dict) and "adjudications" in report:
        return report
    return doc
