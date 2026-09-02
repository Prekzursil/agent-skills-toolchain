"""Offline council-design-note validator for jsonschema 4.10.

The catalog shim at command-center/schema/council-design-note.schema.json is a
single $ref to https://ast-integrate.invalid/... . jsonschema 4.10's RefResolver
tries that URL and raises RefResolutionError, so a probe that validates against
the shim either crashes or (if the exception is swallowed) accepts garbage.

This module inlines platform/schema/receipt.schema.json $defs and the
council-design-note kind pin. All $ref stay #/$defs/... . No network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT = REPO / "platform" / "schema" / "receipt.schema.json"
SHIM = REPO / "command-center" / "schema" / "council-design-note.schema.json"


def load_schema() -> dict[str, Any]:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$comment": (
            "Inlined council-design-note: generic_report plus report.kind pin. "
            "Physical control plane is platform/schema/receipt.schema.json $defs."
        ),
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {
                            "kind": {"const": "council-design-note"},
                        },
                    }
                }
            },
        ],
        "$defs": receipt["$defs"],
    }


def validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def errors(instance: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def validate(instance: Any) -> None:
    errs = errors(instance)
    if errs:
        raise ValueError("schema-invalid: " + errs[0])


def rejects_garbage() -> tuple[bool, int]:
    cases = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    )
    rejected = sum(1 for g in cases if errors(g))
    return rejected == 3, rejected


def shim_exists() -> bool:
    return SHIM.is_file() and SHIM.stat().st_size > 0
