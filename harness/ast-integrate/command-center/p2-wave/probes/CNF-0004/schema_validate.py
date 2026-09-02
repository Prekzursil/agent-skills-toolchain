"""Disk-only jsonschema validator for confirmation-policy.

jsonschema 4.10 on this host still uses RefResolver and would otherwise
GET https://ast-integrate.invalid/... (network). Preload every schema
file under platform/schema and command-center/schema into the store.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/confirmation-policy.schema.json"


@lru_cache(maxsize=1)
def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for folder in (REPO / "platform" / "schema", REPO / "command-center" / "schema"):
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.relative_to(REPO).as_posix()
            store[BASE + rel] = doc
            sid = doc.get("$id")
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


@lru_cache(maxsize=1)
def validator() -> Draft7Validator:
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or BASE + SCHEMA_REL),
        referrer=schema,
        store=_store(),
    )
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list[Any]:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def garbage_rejected() -> bool:
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0004", "state": "SUCCESS"},
    ):
        if not list(validator().iter_errors(garbage)):
            return False
    return True
