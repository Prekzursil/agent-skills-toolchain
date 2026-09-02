#!/usr/bin/env python3
"""Draft 2020-12 validators for CNL-0107 preset records and the design envelope."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema.validators import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LOCAL_SCHEMA = HERE / "council-preset.schema.json"
CATALOG_SCHEMA = (
    REPO / "command-center" / "schema" / "council-preset.schema.json"
)


def load_local_schema() -> dict[str, Any]:
    return json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))


def envelope_validator() -> Draft202012Validator:
    schema = load_local_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def preset_validator() -> Draft202012Validator:
    schema = load_local_schema()
    body = dict(schema["$defs"]["council_preset"])
    body["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(body)
    return Draft202012Validator(body)


def error_messages(validator: Draft202012Validator, doc: object) -> list[str]:
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]
