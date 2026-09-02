#!/usr/bin/env python3
"""Disk-only jsonschema check for CNL-0118 (no network $ref fetch).

System jsonschema is 4.10.3: Draft202012Validator(registry=...) is not
available, so this loads the shim plus its two physical targets into a
RefResolver store keyed by the ast-integrate.invalid $id URIs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-simulation-spec.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "ARC-0001", "state": "SUCCESS", "sentinel": "SUCCESS:X"},
)
_STORE_PATHS = {
    "https://ast-integrate.invalid/command-center/schema/council-simulation-spec.schema.json": (
        REPO / SCHEMA_REL
    ),
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform" / "schema" / "receipt.schema.json"
    ),
}


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for uri, path in _STORE_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(f"schema target missing: {path}")
        store[uri] = json.loads(path.read_text(encoding="utf-8"))
    return store


def validator() -> Draft7Validator:
    store = load_store()
    shim = store[
        "https://ast-integrate.invalid/command-center/schema/council-simulation-spec.schema.json"
    ]
    resolver = RefResolver(base_uri=str(shim.get("$id") or ""), referrer=shim, store=store)
    return Draft7Validator(shim, resolver=resolver)


def schema_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_accepted() -> list[str]:
    bad: list[str] = []
    for item in GARBAGE:
        if not schema_errors(item):
            bad.append(repr(list(item)[:2] if isinstance(item, dict) else item))
    return bad


def main() -> int:
    if len(sys.argv) < 2:
        print("FAILED:CNL-0118-schema-check usage schema_check.py <artifact>")
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"FAILED:CNL-0118-schema-check missing {path}")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNL-0118-schema-check")
        for row in errs[:20]:
            print(" ", row)
        return 1
    accepted = garbage_accepted()
    if accepted:
        print(f"FAILED:CNL-0118-schema-check garbage accepted {accepted}")
        return 1
    print(json.dumps({"ok": True, "errors": 0, "garbage_rejected": len(GARBAGE)}, sort_keys=True))
    print("SUCCESS:CNL-0118-schema-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
