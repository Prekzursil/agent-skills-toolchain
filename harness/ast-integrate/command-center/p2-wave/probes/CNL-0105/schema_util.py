#!/usr/bin/env python3
"""Draft 2020-12 validation for CNL-0105 affected records.

The catalog path command-center/schema/council-preset.schema.json is a generated
$ref shim (generic_report + report.kind=council-preset) with no $defs.preset.
Affected preset records are validated against this unit's working 20-key schema.
The catalog shim is not rewritten.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from common import REPO, SCHEMA_REL

HERE = Path(__file__).resolve().parent
PRESET_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0105/preset.record.schema.json"
)
ENVELOPE_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0105/envelope.schema.json"
)


def load_catalog_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def load_preset_schema() -> dict:
    return json.loads((HERE / "preset.record.schema.json").read_text(encoding="utf-8"))


def load_envelope_schema() -> dict:
    return json.loads((HERE / "envelope.schema.json").read_text(encoding="utf-8"))


def error_count(instance: object, schema: dict | None = None) -> tuple[int, list[str]]:
    if schema is None:
        schema = load_envelope_schema()
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    errs = list(v.iter_errors(instance))
    msgs = [e.message for e in errs]
    return len(errs), msgs


def validate_preset(preset: dict) -> tuple[int, list[str]]:
    return error_count(preset, load_preset_schema())


def validate_envelope(doc: dict) -> tuple[int, list[str]]:
    return error_count(doc, load_envelope_schema())
