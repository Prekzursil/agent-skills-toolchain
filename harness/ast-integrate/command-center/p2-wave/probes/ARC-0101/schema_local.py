#!/usr/bin/env python3
"""Offline validator for the declared conformance-report output schema.

jsonschema 4.10 on this host has no Draft*Validator(registry=) kwarg, and a
bare Draft7Validator of the generated $ref shim tries HTTPS to
ast-integrate.invalid. Load the shim plus its physical targets into a
RefResolver store so validation stays on disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/conformance-report.schema.json"
STORE_PATHS = (
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_schema_and_resolver() -> tuple[dict[str, Any], RefResolver]:
    store: dict[str, dict[str, Any]] = {}
    docs: list[dict[str, Any]] = []
    for rel in STORE_PATHS:
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(f"schema file missing: {rel}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        docs.append(doc)
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    shim = docs[0]
    base = str(shim.get("$id") or (REPO / DECLARED).as_uri())
    return shim, RefResolver(base_uri=base, referrer=shim, store=store)


def validator() -> Draft202012Validator:
    schema, resolver = load_schema_and_resolver()
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(instance: Any) -> list[Any]:
    return list(validator().iter_errors(instance))
