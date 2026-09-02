#!/usr/bin/env python3
"""Offline Draft-07 validator for the catalog audit-finding shim.

jsonschema 4.10.3 on this worktree uses RefResolver and tries the network for
https://ast-integrate.invalid/... . Load those files from disk into the
resolver store and never fetch. platform.lib.schema_resolver needs
jsonschema>=4.18 (referencing.Registry) and is not used here.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/audit-finding.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict:
    store: dict = {}
    for rel in (
        SHIM,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        doc = _load(path)
        uri = str(doc.get("$id") or "")
        constructed = "https://ast-integrate.invalid/" + rel.replace("\\", "/")
        store[constructed] = doc
        if uri:
            store[uri] = doc
    return store


def make_validator(schema_rel: str = SHIM) -> jsonschema.Draft7Validator:
    schema_path = REPO / schema_rel
    schema = _load(schema_path)
    store = disk_store()
    store[str(schema.get("$id") or "")] = schema
    store["https://ast-integrate.invalid/" + schema_rel.replace("\\", "/")] = schema

    def blocked(uri: str):
        raise jsonschema.exceptions.RefResolutionError(f"blocked-remote:{uri}")

    resolver = jsonschema.RefResolver.from_schema(
        schema,
        store=store,
        handlers={"http": blocked, "https": blocked},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: object, schema_rel: str = SHIM) -> list:
    return sorted(
        make_validator(schema_rel).iter_errors(doc),
        key=lambda e: list(e.path),
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("FAILED:schema_offline usage <artifact.json>")
        raise SystemExit(2)
    path = REPO / sys.argv[1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = iter_errors(doc)
    if errs:
        print("FAILED:schema_offline")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    print("SUCCESS:schema_offline VALID")
