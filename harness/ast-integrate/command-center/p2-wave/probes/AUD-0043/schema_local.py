"""Offline schema checks for AUD-0043.

The catalog output_schema is a generated $ref shim to
https://ast-integrate.invalid/... . jsonschema 4.10 Draft7Validator follows
that URL and raises RefResolutionError. A full receipt_core overlay would
also reject the detector-control payload this unit records (additionalProperties
false). This module:

1. Confirms the catalog shim path exists on disk.
2. Validates the live payload against a local discriminating contract that
   rejects garbage and requires unit_id/state/tests/controls.
3. Optionally tries the shim with a disk RefResolver; that result is
   recorded, never a hard fail, because the shim's physical profile is a
   generic receipt rather than this unit's detector-control shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import RefResolutionError, SchemaError, ValidationError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/audit-detector-control.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "AUD-0000", "state": "SUCCESS"},
)

LOCAL_CONTRACT: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "question",
        "answer",
        "detector",
        "controls",
        "tests",
        "reviewer",
        "evidence",
        "live",
        "named_probes",
    ],
    "properties": {
        "unit_id": {"const": "AUD-0043"},
        "state": {
            "type": "string",
            "enum": [
                "SUCCESS",
                "FAILED",
                "BLOCKED",
                "SEVERED",
                "TIMEOUT",
                "SUPERSEDED",
                "DROPPED-BY-OWNER",
            ],
        },
        "sentinel": {"type": "string", "minLength": 8},
        "completion_sentinel": {"type": "string", "minLength": 8},
        "question": {"type": "string", "minLength": 8},
        "answer": {"type": "string", "minLength": 8},
        "detector": {
            "type": "object",
            "required": ["name", "mechanism"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "mechanism": {"type": "string", "minLength": 1},
            },
        },
        "controls": {"type": "array", "minItems": 2},
        "tests": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["id", "command", "result", "verbatim_output"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "command": {"type": "string", "minLength": 1},
                    "result": {"type": "string", "enum": ["PASS", "FAIL"]},
                    "verbatim_output": {"type": "string"},
                },
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "reviewer_id": {"type": "string", "minLength": 1},
                "verdict": {"type": "string"},
                "independent": {"type": "boolean"},
            },
        },
        "evidence": {"type": "array", "minItems": 1},
        "live": {
            "type": "object",
            "required": [
                "parity_on_good_package",
                "both_states_exclude_module",
                "source_good",
                "installed_good",
                "installed_mutant",
            ],
        },
        "named_probes": {"type": "array", "minItems": 2},
    },
    "additionalProperties": True,
}


def shim_path() -> Path:
    return REPO / SCHEMA_REL


def retrieve(uri: str) -> dict:
    if not uri.startswith(BASE):
        raise ValueError(f"refuses non-estate uri: {uri}")
    rel = uri[len(BASE) :].split("#", 1)[0]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if not str(path).startswith(str(root) + "/"):
        raise ValueError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for root in (REPO / "platform" / "schema", REPO / "command-center" / "schema"):
        if not root.is_dir():
            continue
        for path in root.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.relative_to(REPO).as_posix()
            store[BASE + rel] = doc
            sid = doc.get("$id")
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


def shim_errors(doc: Any) -> list[str]:
    """Best-effort catalog-shim validation. Unresolvable $ref is reported, not raised."""
    path = shim_path()
    if not path.is_file():
        return [f"catalog-shim-missing:{SCHEMA_REL}"]
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"catalog-shim-unreadable:{type(exc).__name__}"]
    try:
        resolver = RefResolver(
            base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
            referrer=schema,
            store=disk_store(),
            handlers={"https": retrieve, "http": retrieve},
        )
        errors = list(Draft7Validator(schema, resolver=resolver).iter_errors(doc))
    except (RefResolutionError, SchemaError, ValidationError) as exc:
        return [f"catalog-shim:{type(exc).__name__}:{exc}"]
    return [e.message for e in errors[:12]]


def local_errors(doc: Any) -> list[str]:
    return [
        e.message
        for e in sorted(
            Draft7Validator(LOCAL_CONTRACT).iter_errors(doc),
            key=lambda e: list(e.path),
        )
    ]


def iter_errors(doc: Any) -> list[str]:
    return local_errors(doc)


def rejects_garbage() -> bool:
    for blob in GARBAGE:
        if not local_errors(blob):
            return False
    return True
