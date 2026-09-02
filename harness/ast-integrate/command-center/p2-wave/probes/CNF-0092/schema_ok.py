"""Disk-only council-audit validator (jsonschema 4.10 RefResolver).

The shim at command-center/schema/council-audit.schema.json $ref's
https://ast-integrate.invalid/... which must NOT be fetched. A store of the
physical files plus the draft-2020-12 meta-schema is the whole resolver.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

SHIM = "command-center/schema/council-audit.schema.json"
PHYSICAL = (
    SHIM,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"$schema": "http://json-schema.org/draft-07/schema#", "blob": "x" * 2000},
    {"unit_id": "CNF-0092", "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0092"},
)


def _store(repo: Path) -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PHYSICAL:
        path = repo / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not isinstance(sid, str) or not sid:
            raise ValueError(f"schema {rel} missing $id")
        store[sid] = doc
    meta = Draft202012Validator.META_SCHEMA
    mid = meta.get("$id") or "https://json-schema.org/draft/2020-12/schema"
    store[str(mid)] = meta
    return store


def validator(repo: Path) -> Draft202012Validator:
    schema = json.loads((repo / SHIM).read_text(encoding="utf-8"))

    def refuse(uri: str) -> None:
        raise RefResolutionError(f"no-network:{uri}")

    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=_store(repo),
        cache_remote=False,
        handlers={"https": refuse, "http": refuse},
    )
    return Draft202012Validator(schema, resolver=resolver)


def error_list(repo: Path, doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator(repo).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_accepted(repo: Path) -> Any:
    v = validator(repo)
    for g in GARBAGE:
        if not list(v.iter_errors(g)):
            return g
    return None
