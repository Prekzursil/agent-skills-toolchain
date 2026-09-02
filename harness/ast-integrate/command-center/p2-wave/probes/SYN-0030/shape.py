#!/usr/bin/env python3
"""Local discriminator for SYN-0030.

The catalog output_schema is a $ref shim to https://ast-integrate.invalid/... .
jsonschema Draft7Validator on this image tries HTTPS for that host and never
comes back (same structural fingerprint as BLD-0043 / ARC-0003). G-1 requires
the artifact to parse and the named probes to reject garbage without a
network fetch.
"""
from __future__ import annotations

DISCRIMINATOR = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "kind",
        "directed_counts",
        "join_keys",
        "detector_control",
        "title_collision_control",
        "tests",
        "reviewer",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "SYN-0030"},
        "state": {"const": "SUCCESS"},
        "kind": {"const": "referential-integrity"},
        "sentinel": {
            "type": "string",
            "minLength": 16,
            "pattern": "^SUCCESS:SYN-0030",
        },
        "join_keys": {
            "type": "object",
            "required": ["are_ids"],
            "properties": {"are_ids": {"const": True}},
        },
        "directed_counts": {
            "type": "array",
            "minItems": 8,
            "maxItems": 8,
            "items": {
                "type": "object",
                "required": ["direction", "count", "denominator", "ids"],
                "properties": {
                    "direction": {"type": "string", "minLength": 1},
                    "count": {"type": "integer", "minimum": 0},
                    "denominator": {"type": "integer", "minimum": 0},
                    "ids": {"type": "array"},
                },
            },
        },
        "detector_control": {
            "type": "object",
            "required": [
                "known_good_eight_zeros",
                "all_plants_fired",
                "four_reports_distinct",
            ],
            "properties": {
                "known_good_eight_zeros": {"const": True},
                "all_plants_fired": {"const": True},
                "four_reports_distinct": {"const": True},
            },
        },
        "title_collision_control": {
            "type": "object",
            "required": ["join_keys_are_ids_not_titles"],
            "properties": {
                "join_keys_are_ids_not_titles": {"const": True}
            },
        },
        "tests": {"type": "array", "minItems": 3},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "referential-integrity"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}

GARBAGE = (
    {"totally": "unrelated", "all_consistent": True},
    {"directed_counts": []},
    {},
)
