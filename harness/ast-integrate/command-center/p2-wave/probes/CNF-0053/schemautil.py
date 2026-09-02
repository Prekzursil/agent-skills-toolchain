"""Disk-only $ref resolution for command-center/schema/benchmark-report.schema.json.

jsonschema 4.10 on this host has no referencing.Registry kwarg, so
platform/lib/schema_resolver.py cannot compile. Draft7Validator + a local
RefResolver maps https://ast-integrate.invalid/ onto this worktree instead
of attempting DNS. That is what makes garbage fail closed and a real
receipt pass.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema

from scenario import REPO, SCHEMA_REL

BASE = "https://ast-integrate.invalid/"
META = "https://json-schema.org/draft/2020-12/schema"


def _retrieve(uri: str) -> dict:
    url = uri.split("#", 1)[0]
    if url == META:
        return dict(jsonschema.Draft202012Validator.META_SCHEMA)
    if not url.startswith(BASE):
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing non-local schema uri (no network): {uri}"
        )
    rel = url[len(BASE) :]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if not str(path).startswith(str(root) + os.sep):
        raise jsonschema.exceptions.RefResolutionError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise jsonschema.exceptions.RefResolutionError(
            f"schema uri has no file on disk: {uri} -> {path}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def validator() -> jsonschema.Draft7Validator:
    schema = load_schema()
    resolver = jsonschema.RefResolver(
        base_uri=schema.get("$id") or BASE,
        referrer=schema,
        handlers={"https": _retrieve, "http": _retrieve},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list:
    return list(validator().iter_errors(doc))


def payload(doc: dict) -> dict:
    """Measurement block lives under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and report:
        return report
    ext = doc.get("extensions")
    if isinstance(ext, dict) and ext:
        return ext
    return doc


def file_artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    eol = "LF"
    if b"\r\n" in path.read_bytes():
        eol = "CRLF"
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "exists": True,
        "eol": eol,
        "role": role,
    }
