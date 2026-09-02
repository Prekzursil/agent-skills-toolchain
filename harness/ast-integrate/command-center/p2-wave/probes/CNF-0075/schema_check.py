#!/usr/bin/env python3
"""Disk-only jsonschema Draft7 validation for the catalog output_schema.

This estate's jsonschema is 4.10.3 (no referencing.Registry). A bare
Draft7Validator follows https://ast-integrate.invalid/... over the network
and raises RefResolutionError. Handlers map that URI prefix onto repo files.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/benchmark-report.schema.json"
BASE = "https://ast-integrate.invalid/"


def _retrieve(uri: str) -> dict:
    if not uri.startswith(BASE):
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing non-local schema uri (no network): {uri!r}"
        )
    rel = uri[len(BASE) :].split("#", 1)[0]
    path = REPO / rel
    if not path.is_file():
        raise jsonschema.exceptions.RefResolutionError(
            f"schema uri has no file on disk: {uri!r} -> {path}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def validator() -> Draft7Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or BASE + SCHEMA_REL),
        referrer=schema,
        handlers={"https": _retrieve, "http": _retrieve},
        cache_remote=True,
    )
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: dict):
    return list(validator().iter_errors(doc))


def error_strings(doc: dict) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def report_body(doc: dict) -> dict:
    """Merge report (and extensions) onto a shallow copy so probes can resume."""
    body = dict(doc)
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        body.update(ext)
    rep = doc.get("report")
    if isinstance(rep, dict):
        body.update(rep)
    return body
