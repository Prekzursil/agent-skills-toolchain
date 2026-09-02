"""Local architecture-review gate for ARC-0027.

The catalog shim $ref targets https://ast-integrate.invalid/... . jsonschema
4.10 on this host tries the network and raises RefResolutionError. Physical
receipt_core sets additionalProperties=false, which cannot hold this unit's
domain payload (both_states, activation_paths) without an ADV rebuild of
A4 DESIGN.json. Validate the probe contract locally so garbage is rejected
and emit cannot hang on DNS.
"""
from __future__ import annotations

from typing import Any

import jsonschema

DOMAIN_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "schema_version",
        "sentinel",
        "architecture_id",
        "authoritative_check_epoch",
        "design_present",
        "cloud_ok",
        "both_states",
        "activation_paths",
        "planted_bypass",
        "claims",
        "evidence",
        "reviewer",
        "reviewers",
        "report",
        "tests",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0027"},
        "state": {"const": "SUCCESS"},
        "schema_version": {"const": 1},
        "sentinel": {"const": "SUCCESS:ARC-0027"},
        "architecture_id": {"const": "A4"},
        "authoritative_check_epoch": {"const": "activation"},
        "design_present": {"const": False},
        "cloud_ok": {"const": False},
        "both_states": {
            "type": "object",
            "required": [
                "index_slipped",
                "activation_caught",
                "selection_also_slips",
            ],
            "properties": {
                "index_slipped": {"const": True},
                "activation_caught": {"const": True},
                "selection_also_slips": {"const": True},
            },
        },
        "activation_paths": {"type": "array", "minItems": 2},
        "planted_bypass": {
            "type": "object",
            "required": ["pass"],
            "properties": {"pass": {"const": True}},
        },
        "claims": {"type": "array", "minItems": 3},
        "evidence": {"type": "array", "minItems": 4},
        "reviewers": {"type": "array", "minItems": 2},
        "reviewer": {
            "type": "object",
            "required": [
                "reviewer_id",
                "verdict",
                "independent",
                "scope_not_agreement",
            ],
            "properties": {
                "independent": {"const": True},
                "scope_not_agreement": {"const": True},
                "verdict": {"const": "PASS"},
            },
        },
        "tests": {"type": "array", "minItems": 2},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "architecture-review"},
                "observations": {"type": "array", "minItems": 2},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000, "state": "SUCCESS"},
)


def errors(doc: Any) -> list[str]:
    validator = jsonschema.Draft7Validator(DOMAIN_SCHEMA)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> bool:
    return all(bool(errors(g)) for g in GARBAGE)


def validate_doc(doc: Any) -> None:
    if not garbage_rejected():
        raise SystemExit("FAILED:ARC-0027 schema is vacuous")
    errs = errors(doc)
    if errs:
        raise SystemExit("FAILED:ARC-0027 schema " + "; ".join(errs[:8]))
