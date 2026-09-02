"""Disk-only validator for the CNL-0096 catalog output_schema.

jsonschema 4.10 on this image uses RefResolver and will otherwise GET
https://ast-integrate.invalid/... . Map those $id values onto repo files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/council-detector-spec.schema.json"
PHYSICAL = [
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]


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


def assert_rejects_garbage() -> None:
    for garbage in ({}, {"unit_id": "CNL-0096"}, {"state": "SUCCESS"}):
        if not iter_errors(garbage):
            raise ValueError(f"schema accepted garbage {garbage!r}")


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Detector payload lives under report (receipt_core forbids extra top-level keys)."""
    report = doc.get("report")
    return report if isinstance(report, dict) else {}
