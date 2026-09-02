"""Offline jsonschema helpers for CNF-0027.

The catalog output_schema is a $ref shim onto platform/schema. System
jsonschema 4.10 resolves https://ast-integrate.invalid over the network
and raises RefResolutionError. This module maps those $id values onto
files already in the worktree and adds a local raw-repetition constraint
the physical generic_report does not express.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/benchmark-report.schema.json"
STORE_RELS = (
    SHIM,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)

# Physical generic_report does not constrain benchmarks[].raw_repetitions.
# Catalog tests_required and probe2 both need a summary-only record to fail.
RAW_CONSTRAINT = {
    "$comment": "CNF-0027 local: raw values, not summaries, and a numeric floor",
    "type": "object",
    "required": ["report"],
    "properties": {
        "report": {
            "type": "object",
            "required": ["kind", "benchmarks", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "benchmark-report"},
                "benchmarks": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "object",
                        "required": [
                            "id",
                            "n",
                            "raw_repetitions",
                            "raw_pool",
                            "median",
                            "q1",
                            "q3",
                            "iqr",
                            "noise_floor",
                            "unit",
                        ],
                        "properties": {
                            "id": {"type": "string", "minLength": 1},
                            "n": {"type": "integer", "minimum": 11},
                            "raw_repetitions": {
                                "type": "array",
                                "minItems": 11,
                                "items": {"type": "number"},
                            },
                            "raw_pool": {
                                "type": "array",
                                "minItems": 13,
                                "items": {"type": "number"},
                            },
                            "median": {"type": "number"},
                            "q1": {"type": "number"},
                            "q3": {"type": "number"},
                            "iqr": {"type": "number"},
                            "noise_floor": {"type": "number"},
                            "unit": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        }
    },
}

_catalog_v = None
_raw_v = None


def _store() -> dict:
    out = {}
    for rel in STORE_RELS:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            out[sid] = data
        out["https://ast-integrate.invalid/" + rel] = data
    return out


def catalog_validator():
    global _catalog_v
    if _catalog_v is None:
        shim = json.loads((REPO / SHIM).read_text(encoding="utf-8"))
        resolver = jsonschema.RefResolver.from_schema(shim, store=_store())
        _catalog_v = jsonschema.Draft7Validator(shim, resolver=resolver)
    return _catalog_v


def raw_validator():
    global _raw_v
    if _raw_v is None:
        _raw_v = jsonschema.Draft7Validator(RAW_CONSTRAINT)
    return _raw_v


def _fmt(err) -> str:
    loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{loc}: {err.message}"


def validate_doc(doc: dict) -> list[str]:
    """Return human-readable errors; empty list means both schemas accept doc."""
    msgs = [_fmt(e) for e in catalog_validator().iter_errors(doc)]
    msgs.extend("raw:" + _fmt(e) for e in raw_validator().iter_errors(doc))
    return msgs


def payload(doc: dict) -> dict:
    """Domain measurements live under report (receipt_core additionalProperties false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}

    def pick(key, default):
        val = report.get(key)
        if val not in (None, [], {}):
            return val
        return doc.get(key, default)

    return {
        "benchmarks": pick("benchmarks", []),
        "sampling": pick("sampling", {}),
        "quiescence": pick("quiescence", {}),
        "improvement_claims": pick("improvement_claims", []),
    }
