"""Offline non-vacuous schema for the CNL-0069 design note.

The catalog output_schema is a generated $ref shim:

  command-center/schema/council-design-note.schema.json
    -> https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json
       #/$defs/council-design-note

jsonschema 4.10 on this image follows that $ref over HTTPS. The host does
not resolve, so jsonschema.validate(doc, shim) raises RefResolutionError
rather than ValidationError. That is not a schema check: garbage and a
real note both crash the same way.

This module compiles a local Draft 2020-12 schema that:
  * never leaves the filesystem
  * rejects empty / unrelated / blob garbage
  * requires the fields the named probes actually read
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
CATALOG_SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"

LOCAL_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ast-integrate.invalid/command-center/p2-wave/probes/CNL-0069/local-design-note.schema.json",
    "title": "CNL-0069 0.95-consensus design note (offline, non-vacuous)",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "answer",
        "definition",
        "fixture_results",
        "negative_controls",
        "reviewer",
        "tests",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0069"},
        "state": {"type": "string", "enum": ["SUCCESS"]},
        "sentinel": {"const": "SUCCESS:CNL-0069"},
        "title": {"type": "string", "minLength": 8},
        "question": {"type": "string", "minLength": 16},
        "answer": {"type": "string", "minLength": 32},
        "definition": {
            "type": "object",
            "required": [
                "of_what",
                "population",
                "naive_formula",
                "qualified_predicate",
                "silent_equals_reasoned_dissent",
            ],
            "properties": {
                "of_what": {"type": "string", "minLength": 8},
                "population": {"type": "string", "minLength": 8},
                "naive_formula": {"type": "string", "minLength": 8},
                "qualified_predicate": {"type": "string", "minLength": 8},
                "silent_equals_reasoned_dissent": {"const": False},
            },
        },
        "fixture_results": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "n_population",
                    "n_explicit_agree",
                    "n_silent",
                    "n_reasoned_dissent",
                    "n_token_dissent",
                    "n_abstain",
                    "naive_fraction",
                    "naive_ge_095",
                    "blocking_codes",
                    "stopping_ok",
                ],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "n_population": {"type": "integer", "minimum": 1},
                    "n_explicit_agree": {"type": "integer", "minimum": 0},
                    "n_silent": {"type": "integer", "minimum": 0},
                    "n_reasoned_dissent": {"type": "integer", "minimum": 0},
                    "n_token_dissent": {"type": "integer", "minimum": 0},
                    "n_abstain": {"type": "integer", "minimum": 0},
                    "naive_fraction": {"type": "string", "minLength": 3},
                    "naive_ge_095": {"type": "boolean"},
                    "blocking_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "stopping_ok": {"type": "boolean"},
                },
            },
        },
        "negative_controls": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "verbatim", "fired_on_bad", "silent_on_good"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "verbatim": {"type": "string", "minLength": 16},
                    "fired_on_bad": {"const": True},
                    "silent_on_good": {"const": True},
                },
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent", "method"],
            "properties": {
                "reviewer_id": {"type": "string", "minLength": 1},
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
                "method": {"type": "string", "minLength": 16},
            },
        },
        "tests": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["id", "command", "result"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "command": {"type": "string", "minLength": 8},
                    "result": {"const": "PASS"},
                },
            },
        },
    },
    "additionalProperties": True,
}


def catalog_shim_present() -> bool:
    if not CATALOG_SCHEMA.is_file() or CATALOG_SCHEMA.stat().st_size <= 0:
        return False
    try:
        doc = json.loads(CATALOG_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    ref = str(doc.get("$ref") or "")
    return "artifact-class-profiles.schema.json" in ref and "council-design-note" in ref


def validator() -> Draft202012Validator:
    Draft202012Validator.check_schema(LOCAL_SCHEMA)
    return Draft202012Validator(LOCAL_SCHEMA)


def error_messages(instance: Any) -> list[str]:
    return [e.message for e in validator().iter_errors(instance)]


def validate_note(doc: Any) -> None:
    if not catalog_shim_present():
        raise ValidationError("catalog output_schema shim missing or not a $ref")
    validator().validate(doc)


def garbage_rejected(samples: list[Any] | None = None) -> int:
    if samples is None:
        samples = [{}, {"totally": "unrelated"}, {"x": "x" * 200}]
    n = 0
    v = validator()
    for g in samples:
        if list(v.iter_errors(g)):
            n += 1
    return n
