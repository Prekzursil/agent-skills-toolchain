"""Disk-only conformance-report validation. Never fetch ast-integrate.invalid.

Distro jsonschema 4.10 has no referencing.Registry kwarg, so schema_resolver
validator_for() TypeErrors here. Pivot: RefResolver store of on-disk $id docs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
_SCHEMA_FILES = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def load_store() -> dict[str, dict[str, Any]]:
    store: dict[str, dict[str, Any]] = {}
    for rel in _SCHEMA_FILES:
        path = REPO / rel
        if not path.is_file():
            raise RuntimeError(f"schema missing on disk: {rel}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("$id"), str):
            raise RuntimeError(f"schema missing $id: {rel}")
        store[str(doc["$id"])] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    return store


def validator() -> Draft202012Validator:
    store = load_store()
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def error_list(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_not_vacuous() -> None:
    for garbage in GARBAGE:
        if not error_list(garbage):
            raise RuntimeError(f"schema accepted garbage {list(garbage)[:3]}")


def validate_or_raise(doc: object) -> None:
    assert_not_vacuous()
    errs = error_list(doc)
    if errs:
        raise RuntimeError("schema-invalid\n" + "\n".join(errs[:24]))
