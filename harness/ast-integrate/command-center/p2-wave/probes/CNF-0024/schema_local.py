"""Resolve the repro-report $ref shim from disk (no network)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/repro-report.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def _store() -> dict:
    out: dict = {}
    for rel in STORE_RELS:
        path = REPO / rel
        if not path.is_file():
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        sid = body.get("$id")
        if isinstance(sid, str) and sid:
            out[sid] = body
        out["https://ast-integrate.invalid/" + rel] = body
    return out


def validator():
    path = REPO / SCHEMA_REL
    schema = json.loads(path.read_text(encoding="utf-8"))
    resolver = jsonschema.RefResolver.from_schema(schema, store=_store())
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def iter_errors(doc) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def payload_of(doc: dict) -> dict:
    """Lab fields live under report when the receipt is schema-valid."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "repro-report"
        or "warm_cache_run" in report
        or "defects" in report
    ):
        return report
    return doc
