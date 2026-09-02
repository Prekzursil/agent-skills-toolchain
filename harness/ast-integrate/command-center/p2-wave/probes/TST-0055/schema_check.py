#!/usr/bin/env python3
"""Offline Draft 2020-12 validator for command-center/schema/test-receipt.schema.json.

The catalog shim $ref targets https://ast-integrate.invalid/... which has no DNS.
jsonschema 4.x on this box still uses RefResolver; populate a disk store and
never fetch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/test-receipt.schema.json"
SHIM_URI = "https://ast-integrate.invalid/command-center/schema/test-receipt.schema.json"
STORE_FILES = {
    SHIM_URI: REPO / SCHEMA_REL,
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for uri, path in STORE_FILES.items():
        store[uri] = json.loads(path.read_text(encoding="utf-8"))
    return store


def validator() -> Draft202012Validator:
    store = load_store()
    schema = store[SHIM_URI]
    resolver = RefResolver(base_uri=SHIM_URI, referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:  # noqa: BLE001 — unresolved $ref is a validation failure
        out.append(f"<ref>: {type(exc).__name__}: {exc}")
    return sorted(out)


def assert_valid(doc: Any) -> None:
    errs = errors(doc)
    if errs:
        raise AssertionError("schema rejected document: " + "; ".join(errs[:12]))


def garbage_rejected() -> None:
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "TST-0055", "state": "SUCCESS"},
    ):
        if not errors(garbage):
            raise AssertionError(f"schema accepted garbage keys={list(garbage)[:6]}")


def matrix_from_artifact(doc: dict[str, Any]) -> list[dict[str, Any]]:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    cells = report.get("matrix") or doc.get("matrix") or []
    return [c for c in cells if isinstance(c, dict)]
