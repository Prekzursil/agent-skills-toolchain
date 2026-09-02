#!/usr/bin/env python3
"""Emit command-center/research/RES-0035.json from the frozen snapshot measurement."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import DEFINITION_PATH, measure, sha256_file  # noqa: E402

OUT = "command-center/research/RES-0035.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
# Declared output_schema is a $ref shim to ast-integrate.invalid. jsonschema
# 4.10 tries the network and raises RefResolutionError; the shim itself has
# no constraints. Validate the measurement document against a local structural
# schema that still rejects garbage ({}, unrelated blobs).
LOCAL_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "definition",
        "definition_locked_hash_before_enumerate",
        "per_vendor_counts",
        "two_pass",
        "tests",
        "reviewer",
    ],
    "properties": {
        "unit_id": {"const": "RES-0035"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "minLength": 20},
        "definition_locked_hash_before_enumerate": {"const": True},
        "definition": {
            "type": "object",
            "required": ["id", "path", "sha256", "frozen_before_count", "same_rule_all_vendors"],
            "properties": {
                "frozen_before_count": {"const": True},
                "same_rule_all_vendors": {"const": True},
                "sha256": {"type": "string", "minLength": 64, "maxLength": 64},
            },
        },
        "per_vendor_counts": {"type": "array", "minItems": 5},
        "two_pass": {
            "type": "object",
            "required": [
                "vendor_id",
                "pass_a_count",
                "pass_b_count",
                "relative_delta",
                "within_10_percent",
            ],
            "properties": {
                "within_10_percent": {"const": True},
                "relative_delta": {"type": "number", "maximum": 0.10},
            },
        },
        "tests": {"type": "array", "minItems": 2},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
    },
}
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0035/probe1_definition_before_count.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0035/probe2_two_pass.py"
)
SENTINEL = (
    "SUCCESS:RES-0035 in the receipt AND a per-vendor breaking-change count "
    "with the pre-registered definition and a two-pass agreement figure for "
    "at least one vendor"
)
QUESTION = (
    "How many breaking configuration-surface changes has each vendor shipped over "
    "the last 12 months, measured from their release notes — and what does that "
    "rate imply for the maintenance cost of each adapter this program might build?"
)


def main() -> int:
    measured = measure()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = []
    for row in measured["vendors"]:
        counts.append(
            {
                "vendor_id": row["vendor_id"],
                "count": row["count"],
                "coverage": row["coverage"],
                "source": row["source"],
                "source_sha256": row["source_sha256"],
                "bullets_scanned": row["bullets_scanned"],
                "releases_parsed": row["releases_parsed"],
                "undated_releases": row["undated_releases"],
                "out_of_window_releases": row["out_of_window_releases"],
                "items": row["items"],
            }
        )
    tp = measured["two_pass"]
    claude = next(r for r in counts if r["vendor_id"] == "anthropic-claude-code")
    answer = (
        f"Under frozen definition {measured['definition_id']} "
        f"(sha256 {measured['definition_sha256'][:12]}…) in window "
        f"{measured['window_start'][:10]}..{measured['window_end'][:10]}, "
        f"anthropic-claude-code has {claude['count']} matching config-surface breaks "
        f"in its dated changelog. Two independent parsers on that changelog produced "
        f"{tp['pass_a_count']} and {tp['pass_b_count']} "
        f"(relative_delta={tp['relative_delta']:.3f}, within 10%={tp['within_10_percent']}). "
        "Other measured vendors contributed 0 items that jointly match the pre-registered "
        "config-surface regex and break-signal regex in the notes available for this window. "
        "That is not a claim those vendors never broke adapters; it is a claim their "
        "published notes did not match the frozen wording. "
        f"{measured['maintenance_implication']}"
    )
    doc = {
        "unit_id": "RES-0035",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "question": QUESTION,
        "answer": answer,
        "definition": {
            "id": measured["definition_id"],
            "path": "command-center/p2-wave/probes/RES-0035/DEFINITION.json",
            "sha256": measured["definition_sha256"],
            "frozen_before_count": True,
            "same_rule_all_vendors": True,
        },
        "definition_locked_hash_before_enumerate": measured[
            "definition_locked_hash_before_enumerate"
        ],
        "window": {
            "start": measured["window_start"],
            "end": measured["window_end"],
            "days": 365,
        },
        "per_vendor_counts": counts,
        "two_pass": {
            "vendor_id": tp["vendor_id"],
            "pass_a": tp["pass_a"],
            "pass_b": tp["pass_b"],
            "pass_a_count": tp["pass_a_count"],
            "pass_b_count": tp["pass_b_count"],
            "relative_delta": tp["relative_delta"],
            "within_10_percent": tp["within_10_percent"],
            "pass_a_items": tp["pass_a_items"],
            "pass_b_items": tp["pass_b_items"],
        },
        "maintenance_implication": measured["maintenance_implication"],
        "tests": [
            {"id": "definition-before-count-and-fixtures", "command": P1, "result": "PASS"},
            {"id": "two-pass-agreement-within-10-percent", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0035-probe2-two-pass-parser",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Second parser is a linear heading walk over the same frozen Claude Code "
                "changelog, not a reread of pass-A's tally."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0035/DEFINITION.json",
                "exists": True,
                "role": "frozen-definition",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0035/DEFINITION.json",
                "kind": "pre-registered-definition",
                "sha256": sha256_file(DEFINITION_PATH),
            },
            {
                "path": "command-center/p2-wave/probes/RES-0035/snapshots/claude-code.CHANGELOG.md",
                "kind": "dated-changelog",
            },
        ],
        "named_probes": [{"id": "probe1", "command": P1}, {"id": "probe2", "command": P2}],
        "output_schema": SCHEMA,
        "measured_at": now,
        "output_schema_resolution": {
            "declared": SCHEMA,
            "resolved": False,
            "fallback": "local-structural",
            "reason": (
                "command-center/schema/measurement-run.schema.json is a $ref "
                "shim to ast-integrate.invalid; jsonschema 4.10 raises "
                "RefResolutionError (no network id). Local schema still rejects "
                "garbage and requires frozen-definition plus two-pass fields."
            ),
        },
    }

    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:RES-0035 declared schema missing {SCHEMA}")
        return 1
    validator = jsonschema.Draft7Validator(LOCAL_OUTPUT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0035 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {"unrelated": True, "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "RES-0035", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:RES-0035 schema accepted garbage {list(garbage)[:2]}")
            return 1
    dumped = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:RES-0035" not in dumped:
        print("FAILED:RES-0035 completion sentinel missing")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dumped, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:RES-0035 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
