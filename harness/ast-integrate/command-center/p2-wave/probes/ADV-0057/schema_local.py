"""Disk-only jsonschema resolver for the license-and-rights-record shim.

System jsonschema 4.10.3 cannot retrieve https://ast-integrate.invalid $id
URIs. Load the shim plus its two physical targets into a RefResolver store.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/license-and-rights-record.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "ADV-0057", "state": "SUCCESS", "sentinel": "SUCCESS:ADV-0057"},
)
_STORE_PATHS = {
    "https://ast-integrate.invalid/command-center/schema/license-and-rights-record.schema.json": (
        REPO / SCHEMA_REL
    ),
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform" / "schema" / "receipt.schema.json"
    ),
}


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for uri, path in _STORE_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(f"schema target missing: {path}")
        store[uri] = json.loads(path.read_text(encoding="utf-8"))
    return store


def validator() -> Draft7Validator:
    store = load_store()
    shim = store[
        "https://ast-integrate.invalid/command-center/schema/license-and-rights-record.schema.json"
    ]
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft7Validator(shim, resolver=resolver)


def schema_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_accepted() -> list[str]:
    bad: list[str] = []
    for item in GARBAGE:
        if not schema_errors(item):
            bad.append(repr(list(item)[:2] if isinstance(item, dict) else item))
    return bad
