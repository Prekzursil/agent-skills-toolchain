"""Draft 2020-12 validation helpers for CNL-0005 participant records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "participant.schema.json"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def check_schema_self() -> list[str]:
    doc = load_schema()
    try:
        Draft202012Validator.check_schema(doc)
    except SchemaError as exc:
        return [str(exc)]
    return []


def validator_for(defn: str | None = None) -> Draft202012Validator:
    doc = load_schema()
    # Always wrap. A document $id plus $ref trips the old RefResolver on
    # jsonschema 4.10 (this image) into a relative-URL fetch.
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": doc["$defs"],
        "$ref": f"#/$defs/{defn or 'participant_descriptor'}",
    }
    Draft202012Validator.check_schema(wrapper)
    return Draft202012Validator(wrapper)


def errors_of(instance: Any, defn: str | None = None) -> list[str]:
    v = validator_for(defn)
    return [e.message for e in v.iter_errors(instance)]


def error_count(instance: Any, defn: str | None = None) -> int:
    return len(errors_of(instance, defn))
