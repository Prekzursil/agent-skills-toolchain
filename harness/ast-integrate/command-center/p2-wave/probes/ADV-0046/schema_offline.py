#!/usr/bin/env python3
"""Offline validator for command-center/schema/privacy-dataflow.schema.json.

The catalog shim $ref is https://ast-integrate.invalid/... . jsonschema 4.10.3
uses RefResolver and tries the network. This module loads the shim, the
artifact-class profile, and receipt.schema.json from disk and never fetches.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/privacy-dataflow.schema.json"
STORE_RELS = (
    SHIM,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
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


def local_contract() -> dict:
    """Draft-07 contract that encodes the catalog completion_sentinel.

    Used as the garbage gate. Does not $ref a network URL.
    """
    verdict = {
        "type": "string",
        "enum": ["CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"],
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "schema_version",
            "unit_id",
            "state",
            "sentinel",
            "spec_anchor",
            "min_bytes_threshold",
            "artifacts",
            "evidence",
            "tests",
            "negative_controls",
            "reviewer",
            "report",
            "extensions",
        ],
        "properties": {
            "schema_version": {"const": 1},
            "unit_id": {"const": "ADV-0046"},
            "state": {"const": "SUCCESS"},
            "sentinel": {
                "type": "string",
                "minLength": 40,
                "pattern": "^SUCCESS:ADV-0046",
            },
            "spec_anchor": {"type": "string", "minLength": 3},
            "min_bytes_threshold": {"type": "integer", "minimum": 4096},
            "artifacts": {"type": "array", "minItems": 1},
            "evidence": {"type": "array", "minItems": 2},
            "tests": {"type": "array", "minItems": 1},
            "negative_controls": {"type": "array", "minItems": 1},
            "reviewer": {
                "type": "object",
                "required": ["reviewer_id", "verdict", "independent"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                },
            },
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"const": "privacy-dataflow"},
                    "observations": {"type": "array", "minItems": 1},
                    "control_ids": {"type": "array", "minItems": 1},
                },
            },
            "extensions": {
                "type": "object",
                "required": ["named_probes", "targets", "controls"],
                "properties": {
                    "named_probes": {
                        "type": "array",
                        "minItems": 2,
                        "items": {
                            "type": "object",
                            "required": ["id", "command", "exit_code", "raw_output"],
                            "properties": {
                                "exit_code": {"const": 0},
                                "raw_output": {"type": "string", "minLength": 32},
                            },
                        },
                    },
                    "targets": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["id", "claim", "verdict"],
                            "properties": {"verdict": verdict},
                        },
                    },
                    "controls": {"type": "array", "minItems": 1},
                },
            },
        },
        "additionalProperties": True,
    }


def local_validator() -> jsonschema.Draft7Validator:
    return jsonschema.Draft7Validator(local_contract())


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("FAILED:schema_offline usage <artifact.json>")
        raise SystemExit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        path = REPO / sys.argv[1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    local_errs = sorted(
        local_validator().iter_errors(doc), key=lambda e: list(e.path)
    )
    disk_errs = iter_errors(doc)
    if local_errs or disk_errs:
        print("FAILED:schema_offline")
        for err in (local_errs + disk_errs)[:20]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    print("SUCCESS:schema_offline VALID")
