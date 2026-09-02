"""Offline metric-registry validation plus a unit-local teeth contract.

The catalog output_schema is a generated $ref shim whose $id lives on
https://ast-integrate.invalid/. jsonschema 4.10 on this host tries to fetch
that URL and raises RefResolutionError. This module maps those $ids onto
the files in-tree so emit stays offline, and layers a teeth schema so a
receipt without a seq=0 pin is schema-red.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM_REL = "command-center/schema/foundry-artifact.schema.json"
STORE_FILES = (
    SHIM_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)

# Unit-local contract: the catalog fragment only pins report.kind. G-1 still
# needs a frozen pin recorded before the first score.
TEETH: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "report",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "unit_id": {"const": "WFA-0130"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:WFA-0130"},
        "report": {
            "type": "object",
            "required": [
                "kind",
                "pin",
                "metrics",
                "decision_rule",
                "first_measurement",
                "mutation_control",
                "predicate",
                "observations",
                "control_ids",
            ],
            "properties": {
                "kind": {"const": "metric-registry"},
                "metrics": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "required": ["id", "estimator", "formula"],
                        "properties": {
                            "id": {
                                "enum": [
                                    "correctness",
                                    "coverage",
                                    "recovery",
                                    "usability",
                                ]
                            }
                        },
                    },
                },
                "pin": {
                    "type": "object",
                    "required": [
                        "sha256",
                        "seq",
                        "frozen",
                        "recorded_before_first_measurement",
                    ],
                    "properties": {
                        "seq": {"const": 0},
                        "frozen": {"const": True},
                        "recorded_before_first_measurement": {"const": True},
                        "sha256": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                    },
                },
                "first_measurement": {
                    "type": "object",
                    "required": ["seq", "cited_pin_sha256", "decision"],
                    "properties": {
                        "seq": {"const": 1},
                        "decision": {"const": "REJECT"},
                        "cited_pin_sha256": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                    },
                },
                "mutation_control": {
                    "type": "object",
                    "required": ["runner_reason", "scored"],
                    "properties": {
                        "runner_reason": {"const": "PIN_MISMATCH"},
                        "scored": {"const": False},
                    },
                },
                "decision_rule": {
                    "type": "object",
                    "required": [
                        "accept_iff",
                        "minimum_effect_size",
                        "excluded_from_predicate",
                    ],
                    "properties": {
                        "minimum_effect_size": {"type": "number", "minimum": 0},
                        "excluded_from_predicate": {
                            "type": "array",
                            "items": {"type": "string"},
                            "contains": {"const": "stage_count"},
                        },
                    },
                },
            },
        },
    },
}


def schema_store(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    store: dict[str, Any] = {}
    for rel in STORE_FILES:
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def catalog_validator(repo: Path | None = None) -> jsonschema.Draft7Validator:
    root = repo or REPO
    store = schema_store(root)
    profiles = store["https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json"]
    schema = {
        "$ref": str(profiles.get("$id")) + "#/$defs/metric-registry",
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(profiles.get("$id") or ""),
        referrer=profiles,
        store=store,
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def teeth_validator() -> jsonschema.Draft7Validator:
    jsonschema.Draft7Validator.check_schema(TEETH)
    return jsonschema.Draft7Validator(TEETH)


def _msgs(prefix: str, validator: jsonschema.Draft7Validator, doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator.iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{prefix}:{loc}: {err.message}")
    except jsonschema.RefResolutionError as exc:
        out.append(f"{prefix}:ref-resolution:{exc}")
    return out


def validate_doc(doc: Any, repo: Path | None = None) -> list[str]:
    return _msgs("catalog", catalog_validator(repo), doc) + _msgs(
        "teeth", teeth_validator(), doc
    )


def registry_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "metric-registry" or "pin" in report
    ):
        return report
    return doc
