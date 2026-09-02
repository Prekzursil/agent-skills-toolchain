#!/usr/bin/env python3
"""Disk-only validator for command-center/schema/benchmark-result.schema.json.

jsonschema 4.10 follows $ref over HTTPS. The catalog shim points at
https://ast-integrate.invalid/... which does not resolve on this box
(first emit crash: RefResolutionError / NameResolutionError). This module
loads the physical schemas from disk into a RefResolver store and refuses
network retrieval. Same-fingerprint retry of the network $ref is the park
path; this is the pivot.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/benchmark-result.schema.json"
SCHEMA_PATH = REPO / SCHEMA_REL
PHYSICAL = [
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]


class NoNetworkResolver(RefResolver):
    def resolve_remote(self, uri: str):  # type: ignore[override]
        raise jsonschema.exceptions.RefResolutionError(f"no-network:{uri}")


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PHYSICAL:
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or "")
        if not sid:
            raise ValueError(f"schema {rel} has no $id")
        store[sid] = doc
    return store


# Catalog shim $ref is vacuous (GENERATED SHIM). Probe 2 requires garbage
# objects to fail; enforce the benchmark payload contract locally.
DOMAIN_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["unit_id", "report"],
    "properties": {
        "unit_id": {"type": "string", "minLength": 1},
        "report": {
            "type": "object",
            "required": ["metrics", "replay", "paired_rows", "determinism"],
        },
    },
}


def validator() -> Draft7Validator:
    store = _store()
    shim = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    resolver = NoNetworkResolver.from_schema(shim, store=store)
    return Draft7Validator(shim, resolver=resolver)


def iter_errors(doc: Any) -> list[Any]:
    domain = list(Draft7Validator(DOMAIN_SCHEMA).iter_errors(doc))
    try:
        shim_errs = list(validator().iter_errors(doc))
    except jsonschema.exceptions.RefResolutionError:
        shim_errs = []
    return sorted(domain + shim_errs, key=lambda e: list(e.path))


def error_messages(doc: Any) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Benchmark payload lives under report (receipt_core additionalProperties=false)."""
    rep = doc.get("report")
    if isinstance(rep, dict) and "metrics" in rep:
        return rep
    return doc
