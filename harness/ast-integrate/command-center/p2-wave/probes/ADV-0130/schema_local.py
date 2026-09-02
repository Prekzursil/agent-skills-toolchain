"""Disk-only $ref resolution for novelty-ledger.schema.json.

jsonschema 4.10.3 RefResolver fetches https $ref by default. The catalog shim
points at https://ast-integrate.invalid/... which is not a real host. Map that
prefix onto this worktree. Never DNS, never HTTP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/novelty-ledger.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"
BASE = "https://ast-integrate.invalid/"
META = "https://json-schema.org/draft/2020-12/schema"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"$schema": "http://json-schema.org/draft-07/schema#"},
    {"blob": "x" * 2000},
    {"unit_id": "ADV-0130", "state": "SUCCESS"},
    {"kind": "novelty-ledger"},
)


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


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
    if root not in path.parents and path != root:
        raise jsonschema.exceptions.RefResolutionError(f"schema uri escapes repo: {uri}")
    if not str(path).startswith(str(root) + os.sep) and path != root:
        raise jsonschema.exceptions.RefResolutionError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise jsonschema.exceptions.RefResolutionError(
            f"schema uri has no file on disk: {uri} -> {path}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def validator() -> Draft7Validator:
    shim = _load(SCHEMA_REL)
    profiles = _load(PROFILES_REL)
    receipt = _load(RECEIPT_REL)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver(
        base_uri=shim.get("$id") or BASE,
        referrer=shim,
        store=store,
        handlers={"https": _retrieve, "http": _retrieve},
    )
    return Draft7Validator(shim, resolver=resolver)


def iter_errors(doc: Any) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def error_messages(doc: Any) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def rejects_garbage() -> bool:
    v = validator()
    return all(not v.is_valid(item) for item in GARBAGE)


def payload(doc: dict) -> dict:
    """Domain ledger lives under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("filed") is not None or report.get("kind") == "novelty-ledger"
    ):
        return report
    return doc
