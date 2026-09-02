#!/usr/bin/env python3
"""Offline validator for command-center/schema/permission-report.schema.json.

The catalog shim $ref points at https://ast-integrate.invalid/... . Draft7Validator
on this host (jsonschema 4.10, no referencing) tries to fetch that URL on the
network and raises. This module maps the URI prefix onto the repo tree.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

import inventory as I

BASE = "https://ast-integrate.invalid/"
META = "https://json-schema.org/draft/2020-12/schema"


def _retrieve(uri: str) -> dict:
    if uri == META or uri.startswith("https://json-schema.org/"):
        return dict(Draft202012Validator.META_SCHEMA)
    if not uri.startswith(BASE):
        raise ValueError(f"refusing non-local schema uri: {uri}")
    rel = uri[len(BASE) :].split("#", 1)[0]
    path = I.REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    return json.loads(path.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    schema = json.loads((I.REPO / I.SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or BASE),
        referrer=schema,
        handlers={"https": _retrieve},
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
