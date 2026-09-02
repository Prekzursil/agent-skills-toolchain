"""Validate against the catalog regression-delta schema without a network fetch.

jsonschema 4.10 on this box has no `referencing` package, so platform/lib/
schema_resolver.py cannot import. Resolve https://ast-integrate.invalid/ $refs
from disk via RefResolver instead.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_DECL = "command-center/schema/regression-delta.schema.json"
BASE_URI = "https://ast-integrate.invalid/"
PHYSICAL = [
    "command-center/schema/regression-delta.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _store() -> dict[str, dict[str, Any]]:
    store: dict[str, dict[str, Any]] = {}
    for rel in PHYSICAL:
        data = _load(rel)
        store[BASE_URI + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def _https_handler(uri: str) -> dict[str, Any]:
    if not uri.startswith(BASE_URI):
        raise ValueError(f"refusing non-local schema uri: {uri}")
    rel = uri[len(BASE_URI) :].split("#", 1)[0]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise ValueError(f"schema uri missing on disk: {uri}")
    return json.loads(path.read_text(encoding="utf-8"))


def validator():
    schema = _load(SCHEMA_DECL)
    resolver = RefResolver(
        base_uri=schema.get("$id") or (BASE_URI + SCHEMA_DECL),
        referrer=schema,
        store=_store(),
        handlers={"https": _https_handler},
    )
    return Draft202012Validator(schema, resolver=resolver)


def schema_errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_accepted() -> object | None:
    v = validator()
    for garbage in ({}, {"passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(v.iter_errors(garbage)):
            return garbage
    return None


def require_schema(doc: dict[str, Any], prefix: str) -> None:
    errors = schema_errors(doc)
    if errors:
        raise SystemExit(f"{prefix} schema " + " | ".join(errors[:8]))
    vacuous = garbage_accepted()
    if vacuous is not None:
        raise SystemExit(f"{prefix} schema-vacuous accepted {list(vacuous)[:3]}")
