"""Validate against the catalog calibration-report schema with no network.

jsonschema 4.10 Draft7Validator follows $id/$ref over HTTPS. The catalog shim
points at https://ast-integrate.invalid/... which is not a host. Load the
physical files from disk into a RefResolver store so validation has teeth
(garbage is rejected) without leaving the worktree.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/calibration-report.schema.json"
STORE_RELS = (
    "command-center/schema/calibration-report.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def load_store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        store[f"https://ast-integrate.invalid/{rel}"] = doc
    return store


def validator() -> Draft7Validator:
    schema = load_schema()
    resolver = RefResolver.from_schema(schema, store=load_store())
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: dict) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))
