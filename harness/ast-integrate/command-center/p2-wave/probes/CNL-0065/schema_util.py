"""Disk-only validator for the catalog council-design-note shim.

jsonschema 4.10 Draft7Validator follows $ref over HTTPS. The shim points at
https://ast-integrate.invalid/... which is not a network host. Map those $id
URIs onto the files in platform/schema/ so validation never leaves the disk.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

SHIM = "command-center/schema/council-design-note.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def load_json(repo: Path, rel: str) -> dict:
    return json.loads((repo / rel).read_text(encoding="utf-8"))


def validator(repo: Path) -> Draft7Validator:
    shim = load_json(repo, SHIM)
    profiles = load_json(repo, PROFILES)
    receipt = load_json(repo, RECEIPT)
    store = {
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
        shim["$id"]: shim,
    }
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft7Validator(shim, resolver=resolver)
