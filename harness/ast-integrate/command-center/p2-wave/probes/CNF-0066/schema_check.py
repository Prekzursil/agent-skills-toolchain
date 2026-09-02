#!/usr/bin/env python3
"""Offline validator for command-center/schema/detector-control.schema.json.

jsonschema 4.10 Draft7Validator follows $ref over HTTPS and raises
RefResolutionError against ast-integrate.invalid. This module seeds a
RefResolver store from on-disk $id-bearing schemas and never fetches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/detector-control.schema.json"


def _no_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    roots = (REPO / "command-center" / "schema", REPO / "platform")
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.schema.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            sid = doc.get("$id")
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


def validator() -> Draft202012Validator:
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    store = load_store()
    sid = schema.get("$id")
    if isinstance(sid, str) and sid:
        store[sid] = schema
    resolver = RefResolver(
        base_uri=str(sid or schema_path.as_uri()),
        referrer=schema,
        store=store,
        handlers={"http": _no_remote, "https": _no_remote},
    )
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<resolver>: {exc}")
    return sorted(out)


def garbage_rejected(docs: list[Any] | None = None) -> tuple[int, list[str]]:
    samples = docs or [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"kind": "receipt", "state": "SUCCESS"},
    ]
    rejected = 0
    failures: list[str] = []
    for i, garbage in enumerate(samples):
        errs = iter_errors(garbage)
        if errs:
            rejected += 1
        else:
            failures.append(f"garbage[{i}] accepted")
    return rejected, failures
