"""Disk-only JSON Schema resolver for CNF-0069 (no network $ref fetch)."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/calibration-report.schema.json"
STORE_FILES = {
    "https://ast-integrate.invalid/command-center/schema/calibration-report.schema.json": (
        REPO / SCHEMA_REL
    ),
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}

_VALIDATOR: Draft7Validator | None = None


def validator() -> Draft7Validator:
    global _VALIDATOR
    if _VALIDATOR is not None:
        return _VALIDATOR
    store = {uri: json.loads(path.read_text(encoding="utf-8")) for uri, path in STORE_FILES.items()}
    for path in STORE_FILES.values():
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or "")
        if sid:
            store[sid] = doc
            store[sid.split("#", 1)[0]] = doc
        uri = path.resolve().as_uri()
        store[uri] = doc
        rel = path.relative_to(REPO).as_posix()
        store[rel] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    sid = str(schema.get("$id") or "")
    if sid:
        store[sid] = schema
    resolver = RefResolver.from_schema(schema, store=store)
    inner = Draft7Validator(schema, resolver=resolver)

    class _Wrapped:
        def iter_errors(self, doc):
            errs = list(inner.iter_errors(doc))
            if not errs and (not isinstance(doc, dict) or "unit_id" not in doc):
                class E:
                    path = []
                    message = "missing unit_id"

                errs = [E()]
            return errs

    _VALIDATOR = _Wrapped()  # type: ignore[assignment]
    return _VALIDATOR


def payload(doc: dict) -> dict:
    """Calibration fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "sampling" in report or "bands" in report or "control" in report
    ):
        return report
    return doc


def schema_errors(doc: object) -> list[str]:
    errs = sorted(validator().iter_errors(doc), key=lambda e: list(e.path))
    out = [f"{list(e.path)} {e.message}" for e in errs]
    if not out and (not isinstance(doc, dict) or "unit_id" not in doc):
        return ["[] missing unit_id (garbage/empty)"]
    return out
