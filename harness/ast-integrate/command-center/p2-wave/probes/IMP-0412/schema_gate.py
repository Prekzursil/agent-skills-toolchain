#!/usr/bin/env python3
"""Local Draft-7 gate for IMP-0412 (no network $ref).

command-center/schema/duplicate-report.schema.json is a generated shim whose
$ref points at https://ast-integrate.invalid/... . Distro jsonschema 4.10
tries the network and raises RefResolutionError. G-1 is named probes plus
the catalog artifact, so fail-closed with a local schema that still rejects
garbage and self-declared non-delivery states.
"""
from __future__ import annotations

from typing import Any, Mapping

import jsonschema

SENTINEL = "SENTINEL:IMP-0412:DUPLICATES-FINGERPRINTED"
NOT_DELIVERING = ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT")

LOCAL_GATE: dict[str, Any] = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "catalog_scan",
        "collisions",
        "false_positive_rate",
        "planted_controls",
        "reviewer",
        "report",
        "evidence",
        "tests",
    ],
    "properties": {
        "unit_id": {"const": "IMP-0412"},
        "state": {"type": "string", "not": {"enum": list(NOT_DELIVERING)}},
        "sentinel": {"type": "string", "pattern": r"^SENTINEL:IMP-0412:DUPLICATES-FINGERPRINTED$"},
        "catalog_scan": {
            "type": "object",
            "required": [
                "assembled_work_unit_count",
                "collision_pair_count",
                "compared_pair_count",
                "independent_collision_pair_count",
            ],
            "properties": {
                "assembled_work_unit_count": {"type": "integer", "minimum": 1},
                "collision_pair_count": {"type": "integer", "minimum": 0},
                "compared_pair_count": {"type": "integer", "minimum": 0},
                "independent_collision_pair_count": {"type": "integer", "minimum": 0},
                "too_coarse": {"const": False},
            },
        },
        "collisions": {"type": "array"},
        "false_positive_rate": {
            "type": "object",
            "required": ["false_positives", "denominator", "rate_display"],
            "properties": {
                "false_positives": {"type": "integer", "minimum": 0},
                "denominator": {"type": ["integer", "null"], "minimum": 0},
                "rate_display": {"type": "string", "minLength": 3},
            },
        },
        "planted_controls": {
            "type": "object",
            "required": [
                "exact_duplicate_caught",
                "reworded_duplicate_caught",
                "distinct_pair_did_not_collide",
                "claim_time_caught_donor",
            ],
            "properties": {
                "exact_duplicate_caught": {"const": True},
                "reworded_duplicate_caught": {"const": True},
                "distinct_pair_did_not_collide": {"const": True},
                "claim_time_caught_donor": {"const": True},
            },
        },
        "reviewer": {
            "type": "object",
            "required": [
                "reviewer_id",
                "verdict",
                "independent",
                "requested_blind_sample",
                "available_collisions",
            ],
            "properties": {
                "reviewer_id": {"type": "string", "minLength": 1},
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
                "requested_blind_sample": {"type": "integer", "minimum": 1},
                "available_collisions": {"type": "integer", "minimum": 0},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "duplicate-report"},
                "observations": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["name", "measured", "method", "anchor"],
                    },
                },
                "control_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 1},
        "adv_rebuild_circle": {"const": False},
    },
}

GARBAGE = (
    {"totally": "unrelated"},
    {"blob": "x" * 2000},
    {},
)


def validator() -> jsonschema.Draft7Validator:
    return jsonschema.Draft7Validator(LOCAL_GATE)


def errors_for(doc: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for err in sorted(validator().iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def assert_valid(doc: Mapping[str, Any]) -> None:
    errs = errors_for(doc)
    if errs:
        raise SystemExit("FAILED:IMP-0412 schema errors\n" + "\n".join(errs[:20]))
    v = validator()
    for g in GARBAGE:
        if not list(v.iter_errors(g)):
            raise SystemExit(f"FAILED:IMP-0412 schema accepted garbage {list(g)[:2]}")
    text = str(doc.get("sentinel") or "")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0412 sentinel missing from document")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        raise SystemExit(f"FAILED:IMP-0412 self-declared {doc.get('state')}")
