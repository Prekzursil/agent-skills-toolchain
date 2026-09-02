#!/usr/bin/env python3
"""Offline validator for catalog output_schema portability_report.

Attempt 1 used jsonschema.Draft7Validator on
command-center/schema/receipt.schema.json#/$defs/portability_report with no
store. That $ref targets https://ast-integrate.invalid/... and jsonschema 4.10
GETs it (RefResolutionError / NameResolutionError). Same-fingerprint retry is
parked. This module is the named required_fix: map those $id values onto
platform/schema files in this checkout. Never the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/receipt.schema.json"
PHYSICAL = [
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]
FRAGMENT = (
    "https://ast-integrate.invalid/platform/schema/"
    "artifact-class-profiles.schema.json#/$defs/portability_report"
)
GARBAGE = ({}, {"totally": "unrelated"}, {"blob": "x" * 2000})


def _refuse(uri: str) -> Any:
    raise RefResolutionError(f"offline-refused {uri}")


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PHYSICAL:
        path = REPO / rel
        body = json.loads(path.read_text(encoding="utf-8"))
        sid = str(body.get("$id") or "")
        if sid.startswith("https://ast-integrate.invalid/"):
            store[sid] = body
        store["https://ast-integrate.invalid/" + rel] = body
    return store


def validator() -> jsonschema.Draft7Validator:
    store = _store()
    schema = {"$ref": FRAGMENT}
    resolver = jsonschema.RefResolver(
        base_uri="https://ast-integrate.invalid/command-center/schema/receipt.schema.json",
        referrer=schema,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse, "https": _refuse},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


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
    for garbage in GARBAGE:
        if not iter_errors(garbage):
            raise ValueError(f"schema accepted garbage {garbage!r}")
