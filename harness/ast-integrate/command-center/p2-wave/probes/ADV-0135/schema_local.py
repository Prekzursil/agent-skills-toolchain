"""Offline Draft 2020-12 validator for the evasion-corpus catalog shim.

Never fetches ast-integrate.invalid. jsonschema 4.10.3 RefResolver would
otherwise attempt a network GET on the shim $ref (measured: RefResolutionError).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = REPO / "command-center/schema/evasion-corpus.schema.json"
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform/schema/receipt.schema.json"
GARBAGE = [
    {},
    {"unit_id": "ADV-0135", "state": "SUCCESS"},
    {"blob": "x" * 400},
    {"totally": "unrelated"},
]


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


def schema_errors(doc: dict) -> list[str]:
    validator = load_validator()
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    for g in GARBAGE:
        if not list(validator.iter_errors(g)):
            out.append(f"schema accepted garbage {list(g)[:2]}")
    return sorted(out)
