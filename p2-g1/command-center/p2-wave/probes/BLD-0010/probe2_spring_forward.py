#!/usr/bin/env python3
"""Probe 2: independent spring-forward DST reviewer + schema garbage rejection.

Mechanically different from probe 1: does not re-assert the fall-back 01:30
ordering as its only signal. Repeats the DST case on the opposite
(spring-forward) boundary and checks that the coverage-matrix schema rejects
BLOCKED/empty garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0010.json"
SCHEMA = HERE / "coverage_matrix.schema.json"
UNIT = "BLD-0010"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:BLD-0010" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    spring = R.dst_spring_forward()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    live_errs = list(validator.iter_errors(doc))
    garbage = [
        {},
        {"state": "SUCCESS", "unit_id": "BLD-0010"},
        {
            "state": "BLOCKED",
            "sentinel": "SUCCESS:BLD-0010",
            "unit_id": "BLD-0010",
            "record_type": "CoverageMatrix",
        },
    ]
    garbage_err_counts = [sum(1 for _ in validator.iter_errors(g)) for g in garbage]
    print(
        json.dumps(
            {
                "probe": "probe2-spring-forward-reviewer",
                "spring_pass": spring["pass"],
                "before_utc": spring["before_utc"],
                "after_utc": spring["after_utc"],
                "gap_fold0_utc": spring["gap_fold0_utc"],
                "gap_fold1_utc": spring["gap_fold1_utc"],
                "schema_live_errors": len(live_errs),
                "garbage_err_counts": garbage_err_counts,
                "reviewer_id": (doc.get("reviewer") or {}).get("reviewer_id"),
            },
            sort_keys=True,
        )
    )
    if not spring["pass"]:
        return fail("spring-forward DST not ordered")
    if spring["before_utc"] == spring["after_utc"]:
        return fail("spring-forward collapsed 01:30 and 03:30 to one UTC key")
    if len(live_errs) != 0:
        return fail(f"live artifact schema errors={len(live_errs)} {live_errs[0].message}")
    if any(n <= 0 for n in garbage_err_counts):
        return fail(f"schema vacuous garbage_err_counts={garbage_err_counts}")

    art_spring = doc.get("dst_spring_forward") or {}
    if art_spring.get("stamps") != spring["stamps"]:
        return fail("artifact spring-forward stamps drifted from live rerun")
    tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
    if tests.get("T-DST-SPRING-FORWARD-SUPPORTING", {}).get("result") != "PASS":
        return fail("artifact spring-forward test not PASS")
    if tests.get("T-DST-FALL-BACK", {}).get("result") != "PASS":
        return fail("artifact fall-back test not PASS (context, not the primary signal)")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if reviewer.get("scope_not_agreement") is not True:
        return fail("reviewer.scope_not_agreement is not true")
    if "spring-forward" not in str(reviewer.get("reviewer_id") or "") and "spring" not in str(
        reviewer.get("scope") or ""
    ):
        return fail("reviewer does not name the spring-forward boundary")
    print(
        "spring-forward before="
        + spring["before_utc"]
        + " after="
        + spring["after_utc"]
        + " schema_garbage_rejected="
        + str(garbage_err_counts)
    )
    print("SUCCESS:BLD-0010-probe2 independent spring-forward DST review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
