#!/usr/bin/env python3
"""Offline validator for command-center/schema/audit-metric-baseline.schema.json.

jsonschema 4.10.3 RefResolver tries the network for
https://ast-integrate.invalid/... . Load those files from disk and never fetch.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
        doc = _load(REPO / rel)
        constructed = "https://ast-integrate.invalid/" + rel.replace("\\", "/")
        store[constructed] = doc
        ident = str(doc.get("$id") or "")
        if ident:
            store[ident] = doc
    return store


def make_validator(schema_rel: str = SCHEMA_REL):
    schema = _load(REPO / schema_rel)
    store = disk_store()
    store[str(schema.get("$id") or "")] = schema
    store["https://ast-integrate.invalid/" + schema_rel.replace("\\", "/")] = schema

    def blocked(uri: str):
        raise jsonschema.exceptions.RefResolutionError(f"blocked-remote:{uri}")

    resolver = jsonschema.RefResolver.from_schema(
        schema,
        store=store,
        handlers={"http": blocked, "https": blocked},
    )
    validator_cls = getattr(jsonschema, "Draft202012Validator", jsonschema.Draft7Validator)
    return validator_cls(schema, resolver=resolver)


def iter_errors(doc: object, schema_rel: str = SCHEMA_REL) -> list:
    return sorted(make_validator(schema_rel).iter_errors(doc), key=lambda e: list(e.path))


def error_strings(doc: object) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path)
        out.append((loc + ": " if loc else "") + err.message)
    return out


def garbage_is_rejected() -> bool:
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not iter_errors(garbage):
            return False
    return True
