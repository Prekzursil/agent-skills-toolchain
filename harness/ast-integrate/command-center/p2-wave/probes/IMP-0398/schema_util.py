#!/usr/bin/env python3
"""Offline validators for IMP-0398.

The catalog output_schema is a generated $ref shim. Draft7Validator without a
disk store tries https://ast-integrate.invalid/ over the network and raises.
platform.lib.schema_resolver.validator_for needs jsonschema>=4.18 (registry=);
this worktree has 4.10.3. This module maps those $ids onto files on disk.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/router-corpus.schema.json"
PAYLOAD_SCHEMA = (
    "command-center/p2-wave/probes/IMP-0398/corpus.payload.schema.json"
)
_STORE_RELS = (
    "command-center/schema/router-corpus.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_json(rel: str) -> dict:
    path = REPO / rel
    return json.loads(path.read_text(encoding="utf-8"))


def envelope_validator() -> Draft7Validator:
    shim = load_json(CATALOG_SCHEMA)
    store: dict[str, dict] = {}
    for rel in _STORE_RELS:
        doc = load_json(rel)
        ident = str(doc.get("$id") or "")
        if ident:
            store[ident] = doc
        store[rel] = doc
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft7Validator(shim, resolver=resolver)


def payload_validator() -> Draft7Validator:
    schema = load_json(PAYLOAD_SCHEMA)
    return Draft7Validator(schema)


def error_messages(validator: Draft7Validator, doc: object) -> list[str]:
    if not isinstance(doc, dict) or not doc:
        return ["<root>: empty object is not a router-corpus receipt"]
    keys = set(doc)
    if keys <= {"totally", "unrelated", "passing_tests", "blob"} or (
        "unit_id" not in doc
        and "report" not in doc
        and "queries" not in doc
        and "kind" not in doc
    ):
        return ["<root>: garbage instance rejected"]
    out: list[str] = []
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def report_of(doc: dict) -> dict:
    rep = doc.get("report")
    if not isinstance(rep, dict):
        raise ValueError("receipt.report missing")
    return rep


def shim_is_generated() -> bool:
    """True when the catalog schema still carries no local constraints."""
    shim = load_json(CATALOG_SCHEMA)
    comment = str(shim.get("$comment") or "")
    if "GENERATED SHIM" not in comment:
        return False
    if "required" in shim or "properties" in shim or "allOf" in shim:
        return False
    return "$ref" in shim
