"""Offline validator for command-center/schema/audit-finding.schema.json.

The shim $ref targets https://ast-integrate.invalid/... which has no DNS.
jsonschema 4.10 on this box still uses RefResolver (not referencing.Registry),
so populate a disk store and never fetch.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
SHIM_URI = (
    "https://ast-integrate.invalid/command-center/schema/audit-finding.schema.json"
)
STORE_FILES = {
    SHIM_URI: REPO / SCHEMA_REL,
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}


def load_store() -> dict:
    store = {}
    for uri, path in STORE_FILES.items():
        store[uri] = json.loads(path.read_text(encoding="utf-8"))
    return store


def validator() -> Draft202012Validator:
    store = load_store()
    schema = store[SHIM_URI]
    resolver = RefResolver(base_uri=SHIM_URI, referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc) -> list[str]:
    out = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_valid(doc) -> None:
    errs = errors(doc)
    if errs:
        raise AssertionError("schema rejected document: " + "; ".join(errs[:8]))


def garbage_rejected() -> None:
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "AUD-0025", "state": "SUCCESS"},
    ):
        if not errors(garbage):
            raise AssertionError(f"schema accepted garbage keys={list(garbage)[:6]}")
