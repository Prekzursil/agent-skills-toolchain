#!/usr/bin/env python3
"""Offline Draft 2020-12 validator for the catalog measurement-run shim.

Never fetches ast-integrate.invalid. jsonschema 4.10.3 RefResolver would
otherwise attempt a network GET on the shim $ref.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = REPO / "command-center/schema/measurement-run.schema.json"
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"


def load_validator() -> jsonschema.Draft202012Validator:
    shim = json.loads(SHIM.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    store = {
        str(shim.get("$id")): shim,
        str(profiles.get("$id")): profiles,
        str(receipt.get("$id")): receipt,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def schema_errors(validator, doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
