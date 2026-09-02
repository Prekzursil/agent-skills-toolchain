#!/usr/bin/env python3
"""Validate against the catalog security-report shim using a disk-only $ref store.

jsonschema 4.10 on this host still tries to fetch https://ast-integrate.invalid
and has no Draft202012Validator(registry=) kwarg, so platform/lib/schema_resolver.py
cannot compile. This store maps those $id values onto files already in the tree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/security-report.schema.json"
_STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "CNF-0110", "state": "SUCCESS"},
)


def validator() -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    shim = None
    for rel in _STORE_RELS:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = data.get("$id")
        if not isinstance(ident, str) or not ident:
            raise RuntimeError(f"schema {rel} has no $id")
        store[ident] = data
        if rel == SCHEMA_REL:
            shim = data
    if shim is None:
        raise RuntimeError("security-report shim missing")
    resolver = jsonschema.RefResolver(
        base_uri=str(shim["$id"]),
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def error_messages(doc: object) -> list[str]:
    msgs: list[str] = []
    for err in sorted(validator().iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        msgs.append(f"{loc}: {err.message}")
    return msgs


def rejects_garbage() -> bool:
    v = validator()
    return all(list(v.iter_errors(item)) for item in GARBAGE)


def main() -> int:
    if len(sys.argv) < 2:
        print("FAILED:CNF-0110-schema-check usage schema_check.py <artifact.json>")
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"FAILED:CNF-0110-schema-check missing {path}")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = error_messages(doc)
    if errs:
        print("FAILED:CNF-0110-schema-check")
        for line in errs[:20]:
            print(" ", line)
        return 1
    if not rejects_garbage():
        print("FAILED:CNF-0110-schema-check accepted garbage")
        return 1
    print("SUCCESS:CNF-0110-schema-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
