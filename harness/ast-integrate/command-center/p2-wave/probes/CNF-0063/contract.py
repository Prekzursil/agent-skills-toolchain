#!/usr/bin/env python3
"""Non-vacuous unit-local schema for CNF-0063.

The catalog output_schema (command-center/schema/citation-audit.schema.json)
is a generated $ref shim into platform/schema. A bare Draft7Validator on that
shim either accepts garbage (unresolved $ref) or raises. receipt_core
additionalProperties:false would also reject the unit's claim rows at the
document root, which the named probes read. G-1 is those probes plus the
catalog output_path existing. This schema is the check that actually fires.
Do not rebuild the global citation-audit shim (no ADV rebuild circle).
"""
from __future__ import annotations

from typing import Any

import jsonschema

LABEL_INDEP = "INDEPENDENT-SECOND-SOURCE"
LABEL_SINGLE = "SINGLE-SOURCED"
INDEPENDENT = "INDEPENDENTLY-CORROBORATED"
SINGLE = "SINGLE-SOURCED"

UNIT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "claims",
        "single_sourced_count",
        "independently_corroborated_count",
        "republication_counted_twice_count",
        "circular_citation_count",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0063"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:CNF-0063"},
        "single_sourced_count": {"type": "integer", "minimum": 0},
        "independently_corroborated_count": {"type": "integer", "minimum": 0},
        "republication_counted_twice_count": {"type": "integer", "minimum": 0},
        "circular_citation_count": {"type": "integer", "minimum": 0},
        "claims": {
            "type": "array",
            "minItems": 7,
            "items": {
                "type": "object",
                "required": ["id", "claim", "verdict", "label"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "claim": {"type": "string", "minLength": 1},
                    "verdict": {"enum": [INDEPENDENT, SINGLE]},
                    "label": {"enum": [LABEL_INDEP, LABEL_SINGLE]},
                },
            },
        },
    },
}

REQUIRED_IDS = (
    "C-CIRCULAR-PLANT",
    "C-REPUB-PLANT",
    "C-INDEP-PLANT",
    "C-SHA256-WIDTH",
    "C-DIGEST-HOST",
    "C-CATALOG-PATH",
    "C-SCHEMA-SHIM",
)


def validate_artifact(doc: Any) -> list[str]:
    """Return human-readable errors; empty means the unit-local schema passed."""
    jsonschema.Draft7Validator.check_schema(UNIT_SCHEMA)
    validator = jsonschema.Draft7Validator(UNIT_SCHEMA)
    out = [e.message for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))]
    if out:
        return out
    if not isinstance(doc, dict):
        return ["artifact is not an object"]
    by_id = {r.get("id"): r for r in (doc.get("claims") or []) if isinstance(r, dict)}
    missing = [cid for cid in REQUIRED_IDS if cid not in by_id]
    if missing:
        return [f"missing required claim ids {missing}"]
    unlabeled = []
    for row in doc["claims"]:
        verdict, label = row.get("verdict"), row.get("label")
        ok = (verdict == INDEPENDENT and label == LABEL_INDEP) or (
            verdict == SINGLE and label == LABEL_SINGLE
        )
        if not ok:
            unlabeled.append(row.get("id"))
    if unlabeled:
        return [f"verdict/label pair illegal for {unlabeled}"]
    return []


def assert_rejects_garbage() -> None:
    validator = jsonschema.Draft7Validator(UNIT_SCHEMA)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNF-0063", "state": "SUCCESS"},
        {"blob": "x" * 2000},
    ):
        if validator.is_valid(garbage):
            raise SystemExit(f"FAILED:CNF-0063 schema accepts garbage {list(garbage)[:2]}")
