#!/usr/bin/env python3
"""Strictest executable plugin-manifest parser on this estate.

Claude Code's default loader ignores unrecognized top-level fields and
`claude plugin validate` reports them as warnings. `--strict` promotes those
warnings to errors. There is no `claude` CLI here, so the executable
equivalent is the pinned SchemaStore plugin-manifest schema with
`additionalProperties: false` overlaid on the SAME object that declares
`properties` (Draft-07: a sibling allOf branch would reject every key).

The published schema omits top-level additionalProperties (default true),
which is the both-states mutation: the unmodified vendor schema MUST accept
the unknown-field document or the overlay is not what we are testing.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor" / "claude-code-plugin-manifest.schema.json"
UNKNOWN_FIELD_RE = re.compile(
    r"Additional properties are not allowed \('([^']+)' was unexpected\)"
)


def load_vendor_schema() -> dict[str, Any]:
    schema = json.loads(VENDOR.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("vendor schema is not an object")
    # Keep validation offline: the published $id would otherwise fetch.
    schema.pop("$id", None)
    return schema


def allowed_top_level_fields(schema: dict[str, Any] | None = None) -> frozenset[str]:
    schema = schema if schema is not None else load_vendor_schema()
    props = schema.get("properties")
    if not isinstance(props, dict) or not props:
        raise ValueError("vendor schema has no properties allowlist")
    return frozenset(str(k) for k in props)


def strict_schema(base: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = copy.deepcopy(base if base is not None else load_vendor_schema())
    schema["additionalProperties"] = False
    schema["$comment"] = (
        "TST-0179 strict overlay: additionalProperties=false on the vendor "
        "plugin-manifest schema (equivalent to claude plugin validate --strict)."
    )
    return schema


def unexpected_top_level_fields(
    doc: dict[str, Any], schema: dict[str, Any] | None = None
) -> list[str]:
    allowed = allowed_top_level_fields(schema)
    return sorted(k for k in doc.keys() if k not in allowed)


def _named_from_message(message: str) -> list[str]:
    found: list[str] = []
    for m in UNKNOWN_FIELD_RE.finditer(message):
        found.append(m.group(1))
    return found


def parse_manifest(
    doc: dict[str, Any], *, strict: bool = True
) -> dict[str, Any]:
    """Validate a plugin.json object. Returns a structured verdict.

    Independent naming: jsonschema's additionalProperties message AND a
    set-difference against schema.properties. PASS requires they agree.
    """
    if not isinstance(doc, dict):
        raise TypeError("manifest must be an object")
    base = load_vendor_schema()
    schema = strict_schema(base) if strict else base
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    messages = [e.message for e in errors]
    named_by_parser: list[str] = []
    for e in errors:
        if e.validator == "additionalProperties" and not list(e.absolute_path):
            named_by_parser.extend(_named_from_message(e.message))
    named_by_diff = unexpected_top_level_fields(doc, base)
    accepted = len(errors) == 0
    return {
        "accepted": accepted,
        "strict": strict,
        "error_messages": messages,
        "named_unknown_fields_from_parser": named_by_parser,
        "named_unknown_fields_from_diff": named_by_diff,
        "error_names_field": bool(named_by_parser) and named_by_parser == named_by_diff,
    }
