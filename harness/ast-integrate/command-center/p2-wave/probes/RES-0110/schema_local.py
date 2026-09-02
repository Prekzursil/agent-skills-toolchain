"""Disk-only validator for the RES-0110 catalog output_schema.

jsonschema 4.10 Draft7Validator without a store GETs
https://ast-integrate.invalid/ and raises RefResolutionError. Map those $id
values onto repo files. Domain fields live under report because receipt_core
sets additionalProperties false.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/research-registry.schema.json"
PHYSICAL = [
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PHYSICAL:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or "")
        if sid:
            store[sid] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    meta = dict(Draft202012Validator.META_SCHEMA)
    meta_id = str(meta.get("$id") or "https://json-schema.org/draft/2020-12/schema")
    store[meta_id] = meta
    store["https://json-schema.org/draft/2020-12/schema"] = meta
    return store


def validator() -> Draft202012Validator:
    store = _store()
    schema = store["https://ast-integrate.invalid/" + DECLARED]
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(instance: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_valid(instance: Any) -> None:
    errs = iter_errors(instance)
    if errs:
        raise ValueError("schema errors:\n" + "\n".join(errs[:24]))


def assert_rejects_garbage() -> int:
    rejected = 0
    for garbage in GARBAGE:
        if iter_errors(garbage):
            rejected += 1
        else:
            raise ValueError(f"schema accepted garbage {garbage!r}")
    if rejected != 3:
        raise ValueError(f"schema vacuous garbage_rejected={rejected}")
    return rejected


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Merge report into a view so probes can read register/question/reviewers."""
    report = doc.get("report")
    if isinstance(report, dict):
        merged = dict(doc)
        merged.update(report)
        return merged
    return doc
