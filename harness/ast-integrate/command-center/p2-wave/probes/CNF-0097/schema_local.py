#!/usr/bin/env python3
"""Local non-vacuous contract for CNF-0097's install-report shim.

The catalog output_schema (command-center/schema/install-report.schema.json)
is a generated $ref shim. jsonschema 4.10 follows that $ref over HTTPS to
ast-integrate.invalid and raises RefResolutionError. G-1 requires the
artifact to parse as JSON; this contract still rejects garbage and pins the
live-install fields probe2 re-checks.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/install-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0097 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the container listing "
    "proves no repository checkout was present during the install. Any other "
    "terminal state is FAILED:CNF-0097 <classification> with the diagnostic "
    "tail attached."
)

CONTRACT: dict[str, Any] = {
    "type": "object",
    "required": [
        "answers",
        "container",
        "health_check",
        "install",
        "published_artifact",
        "question",
        "sentinel",
        "state",
        "tests",
        "unit_id",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0097"},
        "state": {"const": "SUCCESS"},
        "sentinel": {
            "type": "string",
            "minLength": 80,
            "pattern": "^SUCCESS:CNF-0097 ",
        },
        "question": {"type": "string", "minLength": 40},
        "answers": {
            "type": "object",
            "required": [
                "install_succeeded",
                "undeclared_system_package_required",
                "windows_separator_assumed",
            ],
            "properties": {
                "install_succeeded": {"const": True},
                "undeclared_system_package_required": {"type": "boolean"},
                "windows_separator_assumed": {"const": False},
            },
        },
        "container": {
            "type": "object",
            "required": [
                "image_digest",
                "repo_checkout_present",
                "repo_markers_found",
                "root_listing",
                "runtime",
            ],
            "properties": {
                "image_digest": {
                    "type": "string",
                    "pattern": "^sha256:[0-9a-f]{64}$",
                },
                "repo_checkout_present": {"const": False},
                "repo_markers_found": {"type": "array", "maxItems": 0},
                "root_listing": {
                    "type": "array",
                    "minItems": 3,
                    "contains": {"const": "artifact"},
                },
                "runtime": {"type": "string", "minLength": 3},
            },
        },
        "install": {
            "type": "object",
            "required": ["success", "transcript"],
            "properties": {
                "success": {"const": True},
                "transcript": {"type": "array", "minItems": 1},
            },
        },
        "health_check": {
            "type": "object",
            "required": ["healthy", "output"],
            "properties": {
                "healthy": {"const": True},
                "output": {"type": "array", "minItems": 1},
            },
        },
        "published_artifact": {
            "type": "object",
            "required": ["bytes", "path", "sha256"],
            "properties": {
                "bytes": {"type": "integer", "minimum": 1},
                "path": {"type": "string", "minLength": 8},
                "sha256": {
                    "type": "string",
                    "minLength": 64,
                    "maxLength": 64,
                    "pattern": "^[0-9a-f]{64}$",
                },
            },
        },
        "tests": {"type": "array", "minItems": 3},
    },
    "additionalProperties": True,
}

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000, "state": "SUCCESS"},
)


def catalog_schema_present() -> bool:
    path = REPO / SCHEMA_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(doc, dict) and bool(doc.get("$ref") or doc.get("$id"))


def validate_doc(doc: dict) -> list[str]:
    errs: list[str] = []
    if not catalog_schema_present():
        errs.append(f"catalog output_schema missing or empty: {SCHEMA_REL}")
    validator = jsonschema.Draft7Validator(CONTRACT)
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        errs.append(f"{loc}: {err.message}")
    if SENTINEL not in json.dumps(doc):
        errs.append("completion_sentinel missing from document")
    listing = ((doc.get("container") or {}).get("root_listing") or [])
    for banned in ("opt", ".git", "command-center"):
        if banned in listing:
            errs.append(f"container.root_listing contains repo name {banned!r}")
    return errs


def contract_rejects_garbage() -> bool:
    validator = jsonschema.Draft7Validator(CONTRACT)
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            return False
    return True
