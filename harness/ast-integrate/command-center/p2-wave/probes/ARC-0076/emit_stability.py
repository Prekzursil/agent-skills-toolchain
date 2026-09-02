#!/usr/bin/env python3
"""Emit command-center/phase3/VERDICT-STABILITY.json for ARC-0076."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = E.OUT_REL
SCHEMA = E.SCHEMA_REL

# Catalog output_schema is a $ref shim to ast-integrate.invalid. Resolving it
# over the network fails closed; a validator that accepts everything is worse
# than a local contract that the named probes actually read.
CONTRACT = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "stability",
        "order_effect",
        "independence",
        "both_states",
        "min_bytes_threshold",
        "tests",
        "negative_controls",
        "reviewer",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0076"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "pattern": "^SUCCESS:ARC-0076$"},
        "stability": {
            "type": "object",
            "required": [
                "probability_same_winner",
                "n_replays",
                "identical_configuration_excluded",
            ],
            "properties": {
                "probability_same_winner": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
                "n_replays": {"type": "integer", "minimum": 2},
                "identical_configuration_excluded": {"const": True},
            },
        },
        "order_effect": {
            "type": "object",
            "required": ["primacy_effect", "n_permutations", "position_bias_measured"],
            "properties": {
                "primacy_effect": {"type": "number", "exclusiveMinimum": 0},
                "n_permutations": {"type": "integer", "minimum": 24},
                "position_bias_measured": {"const": True},
            },
        },
        "independence": {
            "type": "object",
            "required": [
                "seat_ids_disjoint",
                "order_differs",
                "checked_before_results",
            ],
            "properties": {
                "seat_ids_disjoint": {"const": True},
                "order_differs": {"const": True},
                "checked_before_results": {"const": True},
            },
        },
        "both_states": {
            "type": "object",
            "required": ["never_wins"],
            "properties": {"never_wins": {"const": True}},
        },
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "tests": {"type": "array", "minItems": 3},
        "negative_controls": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": ["verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
    },
}


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = E.build_report()
    doc["timestamps"] = {"started_at": now, "ended_at": now, "generated_at": now}
    validator = jsonschema.Draft7Validator(CONTRACT)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0076 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "ARC-0076", "state": "SUCCESS"},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0076 schema accepted garbage {list(g)[:2]}")
            return 1
    if not (REPO / SCHEMA).is_file():
        print("FAILED:ARC-0076 catalog output_schema missing on disk")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ARC-0076 emit self-declared not delivering")
        return 1
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:ARC-0076" not in text:
        print("FAILED:ARC-0076 sentinel missing from artifact text")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest, size = E.digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0076 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"winner={doc['baseline_ranking']['winner']} p={doc['stability']['probability_same_winner']} n={doc['stability']['n_replays']}")
    print("SUCCESS:ARC-0076 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
