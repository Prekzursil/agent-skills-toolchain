#!/usr/bin/env python3
"""Probe 2: dangling-edge FIRE, schema discrimination, independent reviewer.

The reviewer re-runs detector control BEFORE reading SYN-0002.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gate import format_counts, run_paths  # noqa: E402
from paths import (  # noqa: E402
    CLAIMS_CLEAN,
    COMPLETION_SENTINEL,
    GRAPH_DANGLING,
    GRAPH_EMPTY,
    OUT,
    REPO,
    RISKS,
    SCHEMA,
    UNKNOWNS,
)
import reviewer  # noqa: E402


def main() -> int:
    derived = reviewer.evaluate_controls()
    print(
        "reviewer_before_receipt "
        f"orphan={derived['planted_orphan']['observed']} "
        f"cycle={derived['planted_cycle']['observed']} "
        f"clean={derived['clean']['observed']} "
        f"verdict={derived['verdict']}"
    )
    if derived["verdict"] != "PASS":
        print("FAILED:SYN-0002-probe2 independent reviewer did not confirm FIRED/FIRED/SILENT")
        return 1

    dangling = run_paths(GRAPH_DANGLING, CLAIMS_CLEAN, RISKS, UNKNOWNS)
    empty = run_paths(GRAPH_EMPTY, CLAIMS_CLEAN, RISKS, UNKNOWNS)
    print(f"dangling observed={dangling.observed} exit_code={dangling.exit_code}")
    for line in format_counts(dangling.counts):
        print(f"[dangling] {line}")
    print(f"empty_cause observed={empty.observed} exit_code={empty.exit_code}")
    for line in format_counts(empty.counts):
        print(f"[empty_cause] {line}")

    if dangling.observed != "FIRED" or dangling.exit_code == 0:
        print("FAILED:SYN-0002-probe2 dangling edge did not FIRE")
        return 1
    if "dangling-edge" not in {f.code for f in dangling.findings}:
        print("FAILED:SYN-0002-probe2 dangling code missing")
        return 1
    if empty.observed != "FIRED" or "empty-cause" not in {f.code for f in empty.findings}:
        print("FAILED:SYN-0002-probe2 empty cause did not FIRE")
        return 1

    art = REPO / OUT
    schema_path = REPO / SCHEMA
    if not art.is_file() or not schema_path.is_file():
        print("FAILED:SYN-0002-probe2 receipt or schema missing")
        return 1
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0002-probe2 schema errors")
        for e in errs[:8]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}, {"unit_id": "nope"}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:SYN-0002-probe2 schema accepted garbage {list(garbage)[:2]}")
            return 1
    print("schema_ok=True garbage_rejected=True")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:SYN-0002-probe2 completion sentinel absent")
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        print("FAILED:SYN-0002-probe2 reviewer row missing PASS/independent")
        return 1
    if derived["planted_orphan"]["observed"] != "FIRED":
        print("FAILED:SYN-0002-probe2 reviewer/receipt mismatch")
        return 1
    print("SUCCESS:SYN-0002-probe2 dangling+empty-cause+schema+independent-reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
