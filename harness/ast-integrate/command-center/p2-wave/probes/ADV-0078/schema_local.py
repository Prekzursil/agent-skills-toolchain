#!/usr/bin/env python3
"""Disk-only validator for injection-corpus-result.

jsonschema 4.10 follows $ref over HTTPS. A bare Draft7Validator of the
catalog shim tries https://ast-integrate.invalid/... and raises
RefResolutionError (first emit crash). Same-fingerprint retry of that
network fetch is the park path; this module loads the physical schemas
from disk into a RefResolver store and refuses network retrieval.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/injection-corpus-result.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
BASE = "https://ast-integrate.invalid/"
FRAGMENT = "#/$defs/injection-corpus-result"


class NoNetworkResolver(RefResolver):
    def resolve_remote(self, uri: str):  # type: ignore[override]
        raise jsonschema.exceptions.RefResolutionError(f"no-network:{uri}")


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in (DECLARED, PROFILES, RECEIPT):
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        doc = json.loads(path.read_text(encoding="utf-8"))
        posix = rel.replace("\\", "/")
        store[BASE + posix] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator() -> Draft202012Validator:
    store = load_store()
    profiles = store[BASE + PROFILES]
    schema = {"$ref": BASE + PROFILES + FRAGMENT}
    resolver = NoNetworkResolver(
        base_uri=BASE + PROFILES,
        referrer=profiles,
        store=store,
    )
    return Draft202012Validator(schema, resolver=resolver)


def error_messages(instance: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
