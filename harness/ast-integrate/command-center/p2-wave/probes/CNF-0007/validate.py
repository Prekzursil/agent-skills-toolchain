#!/usr/bin/env python3
"""Validate a CNF-0007 receipt against assignment-matrix / generic_report.

This worktree's jsonschema is 4.10.3: Draft202012Validator takes RefResolver,
not referencing.Registry. platform/lib/schema_resolver.py's registry= kwarg
raises TypeError here, so this unit resolves the physical $defs from disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT = REPO / "platform" / "schema" / "receipt.schema.json"
SCHEMA_DECL = "command-center/schema/assignment-matrix.schema.json"
LOCAL = HERE / "assignment-matrix.local.json"
LOCAL_ID = (
    "https://ast-integrate.invalid/command-center/p2-wave/probes/"
    "CNF-0007/assignment-matrix.local.json"
)


def compiled_schema() -> dict[str, Any]:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    defs = receipt.get("$defs")
    if not isinstance(defs, dict) or "generic_report" not in defs:
        raise SystemExit("FAILED:CNF-0007 receipt.schema.json missing generic_report")
    schema = {
        "$id": LOCAL_ID,
        "$schema": "https://json-schema.org/draft-07/schema",
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "type": "object",
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {"kind": {"const": "assignment-matrix"}},
                    }
                },
            },
        ],
        "$defs": defs,
    }
    LOCAL.write_text(
        json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return schema


def validator() -> Draft7Validator:
    return Draft7Validator(compiled_schema())


def validate_doc(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
