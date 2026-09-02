"""Resolve run-ledger $ref onto disk. Never fetch ast-integrate.invalid."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = REPO / "command-center/schema/run-ledger.schema.json"
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"


def _no_remote(uri: str):
    raise jsonschema.exceptions.RefResolutionError(f"blocked-remote:{uri}")


def load_shim() -> dict:
    if not SHIM.is_file() or SHIM.stat().st_size <= 0:
        raise SystemExit(f"FAILED:IMP-0443 declared schema missing {SHIM}")
    doc = json.loads(SHIM.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:IMP-0443 declared schema is not an object")
    return doc


def local_validator() -> jsonschema.Draft7Validator:
    schema = load_shim()
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    store = {
        schema["$id"]: schema,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver(
        base_uri=schema["$id"],
        referrer=schema,
        store=store,
        handlers={"http": _no_remote, "https": _no_remote},
    )
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema, resolver=resolver)
