#!/usr/bin/env python3
"""Disk-only validator for command-center/schema/audit-finding.schema.json.

System jsonschema 4.10 follows $ref with requests.get(). The catalog shim
points at https://ast-integrate.invalid/... which is not a network host.
This store maps those $id values onto the on-disk physical schemas.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/audit-finding.schema.json"
STORE_RELS = (
    SHIM,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "ARC-0001", "state": "SUCCESS", "sentinel": "SUCCESS:X"},
)


def _load(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("$id"), str):
        raise ValueError(f"{rel} missing $id")
    return doc


def validator() -> Draft202012Validator:
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        doc = _load(rel)
        store[str(doc["$id"])] = doc
    shim = store["https://ast-integrate.invalid/" + SHIM]
    resolver = RefResolver(base_uri=str(shim["$id"]), referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def schema_errors(instance: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_accepted() -> list[str]:
    bad: list[str] = []
    for item in GARBAGE:
        if not schema_errors(item):
            bad.append(repr(list(item)[:2] if isinstance(item, dict) else item))
    return bad
