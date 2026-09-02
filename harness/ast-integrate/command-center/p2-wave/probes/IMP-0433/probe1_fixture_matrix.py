#!/usr/bin/env python3
"""Probe 1: metaschema self-check + 12+1 fixture matrix against receipt_core."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from schema_validate import (  # noqa: E402
    KNOWN_BAD_SCHEMA,
    SCHEMA_REL,
    SENTINEL,
    check_schema_fails,
    check_schema_ok,
    error_messages,
    load_fixture,
    load_schema,
)

CONDITIONS = [
    "process/task reached a valid terminal state",
    "expected artifact exists",
    "artifact is non-empty and exceeds a meaningful minimum size",
    "artifact parses against its schema",
    "required sentinel is present",
    "required evidence anchors exist",
    "required tests ran and passed",
    "negative controls or mutations fail as expected",
    "independent reviewer status is PASS",
    "no unresolved P0/P1 defect is attached",
    "output was registered in the artifact manifest",
    "downstream consumers can read it",
]


def main() -> int:
    schema = load_schema()
    ok, why = check_schema_ok(schema)
    if not ok:
        print(json.dumps({"pass": False, "reason": f"metaschema:{why}"}))
        print("FAILED:IMP-0433-probe1 schema failed check_schema")
        return 1
    if not check_schema_fails(KNOWN_BAD_SCHEMA):
        print(json.dumps({"pass": False, "reason": "metaschema-control-inert"}))
        print("FAILED:IMP-0433-probe1 known-bad schema was accepted")
        return 1
    if SENTINEL not in json.dumps(schema):
        print("FAILED:IMP-0433-probe1 schema missing authorship sentinel")
        return 1
    for key in ("portability_report", "matrix_cell", "benchmark_result", "receipt_core"):
        if key not in (schema.get("$defs") or {}):
            print(f"FAILED:IMP-0433-probe1 missing $defs.{key}")
            return 1

    pos = load_fixture("positive.json")
    pos_errs = error_messages(pos, schema)
    if pos_errs:
        print(json.dumps({"pass": False, "positive_errors": pos_errs[:8]}))
        print("FAILED:IMP-0433-probe1 positive fixture INVALID")
        return 1

    rows = []
    holes = []
    for n, text in enumerate(CONDITIONS, 1):
        doc = load_fixture(f"negative-{n:02d}.json")
        errs = error_messages(doc, schema)
        invalid = bool(errs)
        rows.append(
            {
                "condition": n,
                "condition_text": text,
                "invalid": invalid,
                "error_count": len(errs),
                "first_error": errs[0] if errs else "",
            }
        )
        if not invalid:
            holes.append(n)
        print(
            f"T4 cond {n:>2} {'INVALID ok' if invalid else 'VALID  ** SCHEMA HOLE **'} "
            f": {text[:52]}"
        )

    payload = {
        "pass": not holes,
        "probe": "probe1-fixture-matrix",
        "schema": SCHEMA_REL,
        "metaschema_ok": True,
        "metaschema_control_fires": True,
        "positive_valid": True,
        "holes": holes,
        "rows": rows,
    }
    print(json.dumps(payload, sort_keys=True))
    if holes:
        print(f"FAILED:IMP-0433-probe1 schema holes at {holes}")
        return 1
    print("SUCCESS:IMP-0433-probe1 metaschema + 12+1 fixture matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
