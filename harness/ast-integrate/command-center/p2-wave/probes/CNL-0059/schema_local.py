#!/usr/bin/env python3
"""Disk-only jsonschema resolver for the council-detector-spec shim.

jsonschema 4.10 on this host follows https://ast-integrate.invalid/ over
the network and raises. Store the three on-disk schemas by $id instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


class _PinError:
    def __init__(self, message: str):
        self.message = message
        self.path = ("unit_id",)


def validator():
    shim = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    profiles = json.loads((REPO / PROFILES).read_text(encoding="utf-8"))
    receipt = json.loads((REPO / RECEIPT).read_text(encoding="utf-8"))
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=shim["$id"],
        referrer=shim,
        store=store,
    )
    inner = jsonschema.Draft7Validator(shim, resolver=resolver)

    class _Pinned:
        def iter_errors(self, doc):
            for err in inner.iter_errors(doc):
                yield err
            if not isinstance(doc, dict) or not doc.get("unit_id") or not doc.get("state"):
                yield _PinError(
                    "garbage: council-detector-spec instances require unit_id and state"
                )

    return _Pinned()


def iter_errors(doc) -> list:
    return list(validator().iter_errors(doc))
