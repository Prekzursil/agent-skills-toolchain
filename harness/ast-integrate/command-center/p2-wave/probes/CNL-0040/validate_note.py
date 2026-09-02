"""Compile the local CNL-0040 design-note schema (no network $ref)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
LOCAL_SCHEMA = HERE / "council-design-note.schema.json"
GARBAGE = {"totally": "unrelated", "passing_tests": 999999, "blob": "x" * 200}


def load_schema() -> dict:
    return json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))


def validator() -> jsonschema.Draft7Validator:
    schema = load_schema()
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema)


def validate_note(doc: dict) -> None:
    v = validator()
    v.validate(doc)
    if not list(v.iter_errors(GARBAGE)):
        raise RuntimeError("local schema accepted garbage; both-states of the schema failed")
