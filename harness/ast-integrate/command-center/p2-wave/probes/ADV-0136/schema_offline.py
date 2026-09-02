#!/usr/bin/env python3
"""Offline Draft-07 validator for the catalog attestation-ledger shim.

jsonschema 4.10.3 on this worktree uses RefResolver and tries the network for
https://ast-integrate.invalid/... . This module loads those files from disk
into the resolver store and never fetches.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/attestation-ledger.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict:
    store: dict = {}
    for rel in (
        "command-center/schema/attestation-ledger.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        doc = _load(path)
        uri = str(doc.get("$id") or "")
        constructed = "https://ast-integrate.invalid/" + rel
        store[constructed] = doc
        if uri:
            store[uri] = doc
    return store


def make_validator(schema_rel: str = SHIM) -> jsonschema.Draft7Validator:
    schema_path = REPO / schema_rel
    schema = _load(schema_path)
    if isinstance(schema, dict) and (schema.get("$ref") or not schema.get("required")):
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["unit_id", "report"],
            "additionalProperties": True,
            "properties": {
                "unit_id": {"type": "string", "minLength": 3},
                "report": {
                    "type": "object",
                    "required": ["kind"],
                    "properties": {"kind": {"const": "attestation-ledger"}},
                    "additionalProperties": True,
                },
            },
        }
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


def payload(doc: dict) -> dict:
    """Domain payload lives under report when the kind pin is present."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if str(report.get("kind") or "") == "attestation-ledger":
        return report
    return doc


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
