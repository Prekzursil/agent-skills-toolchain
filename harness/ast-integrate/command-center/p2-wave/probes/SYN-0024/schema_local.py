"""Offline validator for the negative-evidence-audit shim.

jsonschema 4.x cannot fetch https://ast-integrate.invalid. Preload the
shim, artifact-class profiles, and receipt_core from disk.
"""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

from paths import REPO, SCHEMA_REL

_STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def make_validator() -> Draft202012Validator:
    store: dict[str, Any] = {}
    for rel in _STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel.replace("\\", "/")] = doc
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def validate_doc(doc: dict[str, Any]) -> list[str]:
    validator = make_validator()
    errs = [
        f"{list(e.absolute_path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    ]
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            errs.append("schema accepted garbage")
            break
    return errs
