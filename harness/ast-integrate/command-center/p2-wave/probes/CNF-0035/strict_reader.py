#!/usr/bin/env python3
"""Strict JSON reader for CNF-0035.

Order of enforcement (must not collapse into last-wins or unknown-field):
  1. Decode object members with object_pairs_hook (every object in the tree).
  2. Exact duplicate keys raise duplicate-key (stdlib json.loads is last-wins).
  3. Case-distinct keys that collide under casefold raise case-collision.
  4. JSON Schema draft-07 with additionalProperties false rejects unknown fields.

A later schema miss must not be used as a substitute for (2) or (3).
"""
from __future__ import annotations

import json
from typing import Any

import jsonschema


class StrictParseError(Exception):
    def __init__(self, classification: str, message: str, key: str | None = None):
        super().__init__(message)
        self.classification = classification
        self.key = key


def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise StrictParseError(
                "duplicate-key",
                (
                    "duplicate key "
                    + repr(key)
                    + " refused (not last-wins overwrite)"
                ),
                key,
            )
        seen[key] = value
    folded: dict[str, str] = {}
    for key in seen:
        fold = key.casefold()
        prior = folded.get(fold)
        if prior is not None and prior != key:
            raise StrictParseError(
                "case-collision",
                (
                    "case-distinct keys "
                    + repr(prior)
                    + " and "
                    + repr(key)
                    + " collide under a case-insensitive client"
                ),
                key,
            )
        folded[fold] = key
    return seen


def decode_strict(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_pairs_hook)
    except StrictParseError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictParseError("schema-invalid", f"JSONDecodeError: {exc}") from exc


def validate_schema(obj: Any, schema: dict[str, Any]) -> None:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.path))
    if not errors:
        return
    first = errors[0]
    path = "/".join(str(p) for p in first.absolute_path) or "<root>"
    raise StrictParseError(
        "unknown-field" if "additional" in (first.message or "").lower() else "schema-invalid",
        f"{path}: {first.message}",
    )


def read_strict(text: str, schema: dict[str, Any] | None = None) -> Any:
    obj = decode_strict(text)
    if schema is not None:
        validate_schema(obj, schema)
    return obj


def read_path(path, schema: dict[str, Any] | None = None) -> Any:
    return read_strict(path.read_text(encoding="utf-8"), schema)


def lenient_loads(text: str) -> Any:
    """CPython json.loads last-wins control. Not the unit parser."""
    return json.loads(text)
