#!/usr/bin/env python3
"""Offline catalog-schema validator for jsonschema 4.10 (no network)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/compatibility-matrix.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def store() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rel in (SCHEMA_REL, PROFILES_REL, RECEIPT_REL):
        doc = _load(rel)
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            out[ident] = doc
    return out


def catalog_shim() -> dict[str, Any]:
    return _load(SCHEMA_REL)


def validator_for(schema: dict[str, Any] | None = None) -> Draft202012Validator:
    sch = schema if schema is not None else catalog_shim()
    st = store()
    ident = sch.get("$id")
    if isinstance(ident, str) and ident:
        st = dict(st)
        st[ident] = sch
    resolver = RefResolver.from_schema(sch, store=st)
    return Draft202012Validator(sch, resolver=resolver)


def schema_errors(doc: Any, schema: dict[str, Any] | None = None) -> list[str]:
    out: list[str] = []
    for err in validator_for(schema).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def bound_verdict_schema() -> dict[str, Any]:
    """Catalog shim plus a local can/cannot pin on report.encodings_real.

    The generated compatibility-matrix shim does not constrain encoding
    verdicts. Probe 2 binds that honesty check here (RES-0031 pattern)
    instead of rebuilding the global schema (ADV circle).
    """
    bound = json.loads(json.dumps(catalog_shim()))
    bound["properties"] = {
        "report": {
            "type": "object",
            "properties": {
                "encodings_real": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["verdict"],
                        "properties": {
                            "verdict": {"type": "string", "enum": ["can", "cannot"]},
                            "per_entry": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["verdict"],
                                    "properties": {
                                        "verdict": {
                                            "type": "string",
                                            "enum": ["can", "cannot"],
                                        }
                                    },
                                },
                            },
                        },
                    },
                }
            },
            "required": ["encodings_real"],
        }
    }
    return bound


def domain_get(doc: dict[str, Any], key: str, default: Any = None) -> Any:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if key in report and report[key] is not None:
        return report[key]
    return doc.get(key, default)
