#!/usr/bin/env python3
"""Probe 1: planted controls (both-states detector, not a one-sided green).

Catalog tests_required:
  * assertion-free test in a scratch copy is caught
  * only-assert-in-dead-branch is caught by coverage (assert line uncovered)
  * zero-length benchmark input is caught by runtime size, not fixture name
  * well-formed asserting test is not flagged
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0041.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0041-probe1 {msg}")
    return 1


def main() -> int:
    ctrl = C.run_planted_controls()
    for row in ctrl["controls"]:
        print(f"control {row['id']} {row['result']} {row['evidence']}")
        if row["result"] != "PASS":
            return fail(f"{row['id']} did not PASS")
    if not ctrl["all_pass"]:
        return fail("planted controls not all PASS")

    by_fn = {r["function"]: r for r in ctrl["planted"]["findings"]}
    if "test_c4_well_formed" in by_fn:
        return fail("negative control test_c4_well_formed was flagged")
    if "test_c5_raise_assertion_error" in by_fn:
        return fail("negative control test_c5_raise_assertion_error was flagged")
    if "test_regex_trap_comment" in by_fn:
        return fail("regex trap (comment/string assert True) was flagged")
    if "test_bench_named_empty_but_full" in by_fn:
        return fail("filename trap empty.json (3 items) was flagged as tautology")

    c3 = by_fn["test_c3_bench_full_corpus"]
    if c3.get("fixture_basename") != "full_corpus.json":
        return fail("empty-input fixture was not the misleading full_corpus.json")
    if int(c3["measured_input_size"]) != 0:
        return fail("measured_input_size is not 0")
    if c3.get("fixture_name_not_consulted") is not True:
        return fail("fixture_name_not_consulted is not true")

    c2 = by_fn["test_c2_unreachable_assert"]
    taut = C.PLANTED / "execable" / "test_tautologies.py"
    hits = C.execute_under_coverage(taut, "test_c2_unreachable_assert")
    assert_line = int(c2.get("assert_line") or 0)
    if not assert_line or assert_line in hits:
        return fail(f"assert line {assert_line} was covered hits={sorted(hits)}")
    print(f"coverage assert_line={assert_line} uncovered hits={sorted(hits)}")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:BLD-0041" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    ids = {c["id"]: c["result"] for c in (doc.get("controls") or [])}
    for needed in (
        "T-NO-ASSERT-PLANTED",
        "T-UNREACHABLE-COVERAGE",
        "T-EMPTY-BENCH-RUNTIME-SIZE",
        "T-NEGATIVE-WELL-FORMED",
    ):
        if ids.get(needed) != "PASS":
            return fail(f"receipt control {needed} is {ids.get(needed)}")
    rec_fns = {
        f["function"]: f["reason_class"]
        for f in doc.get("findings") or []
        if f.get("origin") == "planted-control"
    }
    live_fns = {k: v["reason_class"] for k, v in by_fn.items()}
    if rec_fns != live_fns:
        return fail(f"receipt planted findings != live detector {rec_fns} vs {live_fns}")

    print("SUCCESS:BLD-0041-probe1 planted controls coverage filename-trap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
