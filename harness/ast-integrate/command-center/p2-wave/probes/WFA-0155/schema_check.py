"""Validate WFA-0155 artifacts against the catalog translation-oracle schema.

jsonschema 4.10 on this box has no referencing `registry=` kwarg, so this
uses a disk-only RefResolver over the physical control-plane files. No
network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROFILES = REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
RECEIPT = REPO / "platform" / "schema" / "receipt.schema.json"
SCHEMA = (
    "command-center/schema/foundry-artifact.schema.json#/$defs/translation-oracle"
)
GARBAGE = (
    {},
    {"unit_id": "WFA-0155", "state": "SUCCESS", "sentinel": "SUCCESS:WFA-0155"},
    {"blob": "x" * 400},
)


def validator() -> Draft202012Validator:
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    store = {profiles["$id"]: profiles, receipt["$id"]: receipt}
    schema = {"$ref": profiles["$id"] + "#/$defs/translation-oracle"}
    resolver = RefResolver(
        base_uri=profiles["$id"] + "/", referrer=profiles, store=store
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def rejects_garbage() -> bool:
    for g in GARBAGE:
        if not errors(g):
            return False
    return True
