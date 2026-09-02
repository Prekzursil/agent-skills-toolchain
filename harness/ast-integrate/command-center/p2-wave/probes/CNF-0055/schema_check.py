#!/usr/bin/env python3
"""Offline validator for command-center/schema/regression-delta.schema.json."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/regression-delta.schema.json"
PHYSICAL = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


class OfflineResolver(RefResolver):
    def resolve_remote(self, uri: str):  # noqa: ARG002
        raise RefResolutionError(f"offline: refusing remote fetch {uri!r}")


def load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = load_json(SCHEMA_REL)
    store: dict[str, dict] = {}
    for rel in PHYSICAL:
        doc = load_json(rel)
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    resolver = OfflineResolver(
        base_uri=str(shim.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL)),
        referrer=shim,
        store=store,
    )
    return Draft202012Validator(shim, resolver=resolver)


def errors(doc) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def refuse_garbage() -> list[str]:
    accepted: list[str] = []
    v = validator()
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0055", "state": "SUCCESS"},
        {"report": {"kind": "regression-delta"}},
    ):
        if not list(v.iter_errors(garbage)):
            accepted.append(str(list(garbage)[:2]))
    return accepted
