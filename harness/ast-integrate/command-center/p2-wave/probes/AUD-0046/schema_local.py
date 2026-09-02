"""Offline validator for AUD-0046.

Catalog command-center/schema/audit-detector-control.schema.json is a generated
shim whose $ref is https://ast-integrate.invalid/... . jsonschema 4.10.3
RefResolver tries the network (RefResolutionError / NameResolutionError). G-1
does not require that hop. Compile the physical profile from on-disk $defs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM_REL = "command-center/schema/audit-detector-control.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"
KIND = "audit-detector-control"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)

_VALIDATOR = None


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def _validator() -> jsonschema.Draft7Validator:
    global _VALIDATOR
    if _VALIDATOR is not None:
        return _VALIDATOR
    receipt = json.loads((REPO / RECEIPT_REL).read_text(encoding="utf-8"))
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {"kind": {"const": KIND}},
                    }
                }
            },
        ],
        "$defs": receipt["$defs"],
    }
    _VALIDATOR = jsonschema.Draft7Validator(schema)
    return _VALIDATOR


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in _validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def validate(doc: Any) -> None:
    errs = errors(doc)
    if errs:
        raise jsonschema.ValidationError("; ".join(errs[:12]))


def rejects_garbage() -> bool:
    v = _validator()
    return all(list(v.iter_errors(g)) for g in GARBAGE)


def detectors_from(doc: dict) -> list[dict]:
    if not isinstance(doc, dict):
        return []
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    for blob in (report, doc):
        rows = blob.get("detectors")
        if isinstance(rows, list) and rows:
            return [r for r in rows if isinstance(r, dict)]
    return []


def report_kind(doc: dict) -> str:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return str(report.get("kind") or doc.get("kind") or "")
