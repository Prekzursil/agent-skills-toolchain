#!/usr/bin/env python3
"""Named probe 1: PASS, FAIL, and ERROR are three distinct live verdicts.

Does not score skip accounting (that is probe 2). Re-executes the three
fixture suites through the runner and checks the artifact recorded the
same live values.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import runner as R  # noqa: E402

UNIT = "ARC-0098"
ART = REPO / "command-center" / "phase4" / "conformance" / "ARC-0098.json"
SCHEMA = REPO / "command-center" / "schema" / "conformance-report.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ARC-0098" not in json.dumps(doc):
        return fail("sentinel absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            return fail("schema accepts garbage", probe)
    schema_hits = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if schema_hits:
        return fail(
            "artifact schema",
            [{"path": list(e.path), "msg": e.message} for e in schema_hits[:8]],
        )

    live = R.run_report(
        R.DEFAULT_SUITES, select=["known-pass", "known-fail", "known-error"]
    )
    by_id = {row["id"]: row["verdict"] for row in live["suites"]}
    if by_id.get("known-pass") != "PASS":
        return fail("known-pass not PASS", by_id)
    if by_id.get("known-fail") != "FAIL":
        return fail("known-fail not FAIL", by_id)
    if by_id.get("known-error") != "ERROR":
        return fail("known-error not ERROR", by_id)
    distinct = {by_id["known-pass"], by_id["known-fail"], by_id["known-error"]}
    if distinct != {"PASS", "FAIL", "ERROR"}:
        return fail("three-state collapsed", by_id)
    if live["overall_verdict"] != "ERROR" or live["exit_code"] != 2:
        return fail("ERROR does not outrank FAIL in aggregate", live)

    if R.classify_process(1, "SUITE-FAIL: planted", "", False, False) != "FAIL":
        return fail("SUITE-FAIL marker not classified FAIL")
    if (
        R.classify_process(1, "", "Traceback (most recent call last):", False, False)
        != "ERROR"
    ):
        return fail("traceback exit 1 classified as FAIL (collapsed)")
    if R.classify_process(0, "SUITE-PASS", "", False, False) != "PASS":
        return fail("SUITE-PASS not classified PASS")

    rec = (doc.get("control_runs") or {}).get("three_state") or {}
    rec_by = {row["id"]: row["verdict"] for row in rec.get("suites") or []}
    if rec_by != by_id:
        return fail("artifact three_state drift", {"live": by_id, "recorded": rec_by})

    mutant_vals = {("FAIL" if v == "ERROR" else v) for v in by_id.values()}
    if mutant_vals == distinct:
        return fail("collapse mutant still three-valued")
    if "ERROR" in mutant_vals:
        return fail("collapse mutant retained ERROR")

    payload = {
        "pass": True,
        "probe": "probe1-three-state",
        "unit_id": UNIT,
        "live_verdicts": by_id,
        "distinct": sorted(distinct),
        "aggregate": live["overall_verdict"],
        "exit_code": live["exit_code"],
        "traceback_is_error": True,
        "fail_marker_is_fail": True,
        "collapse_mutant_distinct": sorted(mutant_vals),
        "schema_garbage_rejected": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"pass={by_id['known-pass']} fail={by_id['known-fail']} "
        f"error={by_id['known-error']} distinct=3 aggregate={live['overall_verdict']}"
    )
    print("SUCCESS:ARC-0098-probe1 three-state pass/fail/error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
