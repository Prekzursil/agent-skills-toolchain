"""Disk-only jsonschema resolver for the catalog council-design-note $ref shim.

The declared schema $ref's https://ast-integrate.invalid/... which is not a
network host. jsonschema 4.10 would otherwise call requests.get and raise.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = REPO / "command-center" / "schema" / "council-design-note.schema.json"
PROFILES = REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform" / "schema" / "receipt.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _refuse_remote(uri: str):
    raise jsonschema.exceptions.RefResolutionError(f"refused-remote:{uri}")


def disk_validator(schema: dict | None = None) -> Draft7Validator:
    schema = schema if schema is not None else _load(DECLARED)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {
        schema.get("$id"): schema,
        profiles.get("$id"): profiles,
        receipt.get("$id"): receipt,
        "https://ast-integrate.invalid/command-center/schema/council-design-note.schema.json": schema,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = RefResolver.from_schema(
        schema,
        store=store,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return Draft7Validator(schema, resolver=resolver)
