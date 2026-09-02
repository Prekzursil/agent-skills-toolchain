"""Disk-only validator for confirmation-audit.schema.json.

The catalog shim $ref points at https://ast-integrate.invalid/... which
Draft7Validator would fetch from the network. jsonschema 4.10 on this
worktree also cannot use platform/lib/schema_resolver.py (no registry=
kwarg). Resolve the three physical files from disk only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/confirmation-audit.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"
BASE = "https://ast-integrate.invalid/"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _retrieve_https(uri: str) -> dict:
    path = uri.split("#", 1)[0]
    if not path.startswith(BASE):
        raise ValueError(f"non-local schema uri: {uri}")
    rel = path[len(BASE) :]
    target = (REPO / rel).resolve()
    root = REPO.resolve()
    if root not in target.parents and target != root:
        raise ValueError(f"schema uri escapes repo: {uri}")
    if not target.is_file():
        raise ValueError(f"schema uri missing on disk: {uri}")
    return json.loads(target.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = _load(SCHEMA_REL)
    profiles = _load(PROFILES_REL)
    receipt = _load(RECEIPT_REL)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver(
        base_uri=shim["$id"],
        referrer=shim,
        store=store,
        handlers={"https": _retrieve_https},
    )
    return Draft202012Validator(shim, resolver=resolver)


def iter_errors(doc: Any) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def error_messages(doc: Any) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def rejects_garbage() -> bool:
    v = validator()
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"$schema": "http://json-schema.org/draft-07/schema#"},
        {"unit_id": "CNF-0125", "state": "SUCCESS"},
    )
    return all(not v.is_valid(item) for item in garbage)
