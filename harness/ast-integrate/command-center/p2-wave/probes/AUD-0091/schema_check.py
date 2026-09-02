#!/usr/bin/env python3
"""Offline validator for command-center/schema/audit-detector-control.schema.json.

The catalog file is a generated $ref shim to ast-integrate.invalid.
jsonschema 4.10.3 RefResolver would otherwise HTTPS-GET that host
(measured: RefResolutionError / NameResolutionError). G-1 does not
require that hop and forbids an ADV rebuild of the shim.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM_REL = "command-center/schema/audit-detector-control.schema.json"
_FILES = (
    SHIM_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {"unit_id": "AUD-0091", "state": "SUCCESS"},
    {"totally": "unrelated", "passing_tests": 999999},
    {},
)


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in _FILES:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or "").split("#", 1)[0]
        if sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    return store


def validator() -> jsonschema.Draft202012Validator:
    shim = json.loads((REPO / SHIM_REL).read_text(encoding="utf-8"))
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or SHIM_REL),
        referrer=shim,
        store=load_store(),
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def error_list(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def validate(doc: object) -> None:
    validator().validate(doc)


def garbage_error_counts() -> list[int]:
    v = validator()
    return [len(list(v.iter_errors(g))) for g in GARBAGE]


def rejects_garbage() -> bool:
    return all(c > 0 for c in garbage_error_counts())


__all__ = [
    "GARBAGE",
    "SHIM_REL",
    "ValidationError",
    "error_list",
    "garbage_error_counts",
    "rejects_garbage",
    "validate",
    "validator",
]
