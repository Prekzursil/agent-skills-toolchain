"""Disk-only validator for command-center/schema/owner-brief.schema.json.

jsonschema 4.10.3 follows $ref over HTTPS to ast-integrate.invalid and
raises RefResolutionError. Store the three on-disk $id documents and
never open a socket.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/owner-brief.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "SYN-0045", "state": "SUCCESS"},
)


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _store() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rel in STORE_RELS:
        raw = _load(rel)
        sid = raw.get("$id")
        if not isinstance(sid, str) or not sid:
            raise RuntimeError(f"{rel} has no $id")
        out[sid] = raw
    return out


def validator() -> Draft202012Validator:
    store = _store()
    schema = store["https://ast-integrate.invalid/command-center/schema/owner-brief.schema.json"]
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def schema_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_accepted() -> list[str]:
    accepted: list[str] = []
    for blob in GARBAGE:
        if not schema_errors(blob):
            accepted.append(str(list(blob)[:1] if isinstance(blob, dict) else type(blob)))
    return accepted
