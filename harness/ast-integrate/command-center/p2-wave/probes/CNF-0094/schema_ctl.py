#!/usr/bin/env python3
"""Offline validation of the physical calibration-report profile.

jsonschema 4.10.3 on this host has no referencing.Registry keyword, and the
catalog shim $ref (ast-integrate.invalid) is not retrievable. Compile the
profile from on-disk $defs instead of touching the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/calibration-report.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"

_VALIDATOR = None


def _validator():
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
                        "properties": {"kind": {"const": "calibration-report"}},
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


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live on report/extensions under additionalProperties:false."""
    merged: dict[str, Any] = {}
    for blob in (doc.get("extensions"), doc.get("report"), doc):
        if isinstance(blob, dict):
            merged.update(blob)
    return merged
