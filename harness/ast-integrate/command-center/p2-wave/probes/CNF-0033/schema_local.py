"""Resolve the benchmark-report $ref shim from disk (no network).

jsonschema 4.10 on this host tries to fetch ast-integrate.invalid over HTTPS
and raises RefResolutionError. Named probes and emit must use this module.

The catalog schema is receipt_core + generic_report + report.kind pin. It does
not know CNF-0033 claim rows. overlay_validator() allOfs that schema with the
unit rule: NOT-CHECKED requires missing_raw_file; MATCH/MISMATCH/UNMEASURABLE
require a numeric recomputed_value.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/benchmark-report.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SHIM_ID = (
    "https://ast-integrate.invalid/command-center/schema/benchmark-report.schema.json"
)

CLAIM_CONSTRAINTS: dict[str, Any] = {
    "type": "object",
    "required": ["report"],
    "properties": {
        "report": {
            "type": "object",
            "required": ["kind", "claims", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "benchmark-report"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "claims": {
                    "type": "array",
                    "minItems": 4,
                    "items": {
                        "type": "object",
                        "required": ["id", "verdict", "raw_file"],
                        "properties": {
                            "id": {"type": "string", "minLength": 1},
                            "verdict": {
                                "enum": [
                                    "MATCH",
                                    "MISMATCH",
                                    "UNMEASURABLE",
                                    "NOT-CHECKED",
                                ]
                            },
                            "raw_file": {"type": "string", "minLength": 1},
                            "missing_raw_file": {"type": "string", "minLength": 1},
                            "recomputed_value": {"type": ["number", "null"]},
                        },
                        "allOf": [
                            {
                                "if": {
                                    "required": ["verdict"],
                                    "properties": {
                                        "verdict": {"const": "NOT-CHECKED"}
                                    },
                                },
                                "then": {
                                    "required": ["missing_raw_file"],
                                    "properties": {
                                        "recomputed_value": {"type": "null"}
                                    },
                                },
                            },
                            {
                                "if": {
                                    "required": ["verdict"],
                                    "properties": {
                                        "verdict": {
                                            "enum": [
                                                "MATCH",
                                                "MISMATCH",
                                                "UNMEASURABLE",
                                            ]
                                        }
                                    },
                                },
                                "then": {
                                    "required": ["recomputed_value"],
                                    "properties": {
                                        "recomputed_value": {"type": "number"}
                                    },
                                },
                            },
                        ],
                    },
                },
            },
        }
    },
}


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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


def catalog_schema() -> dict:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def catalog_validator():
    schema = catalog_schema()
    resolver = jsonschema.RefResolver.from_schema(schema, store=_store())
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def overlay_schema() -> dict:
    return {"allOf": [{"$ref": SHIM_ID}, CLAIM_CONSTRAINTS]}


def overlay_validator():
    schema = overlay_schema()
    resolver = jsonschema.RefResolver.from_schema(schema, store=_store())
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validator():
    """Discriminating validator used by emit and named probes."""
    return overlay_validator()


def iter_errors(doc) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def catalog_iter_errors(doc) -> list:
    return sorted(
        catalog_validator().iter_errors(doc), key=lambda e: list(e.path)
    )


def payload_of(doc: dict) -> dict:
    """Lab fields live under report when the receipt is schema-valid."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "benchmark-report" or "claims" in report
    ):
        return report
    return doc


def claims_of(doc: dict) -> list:
    payload = payload_of(doc)
    rows = payload.get("claims")
    if isinstance(rows, list):
        return rows
    rows = doc.get("claims") if isinstance(doc, dict) else None
    return rows if isinstance(rows, list) else []
