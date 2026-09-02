#!/usr/bin/env python3
"""Probe 1: line-set delta with coverage enabled on both states."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage_delta as C  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0061-coverage-line-delta.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0061-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = __import__("json").loads(text)
    if doc.get("unit_id") != "CNF-0061":
        print("FAILED:CNF-0061-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0061" not in text:
        print("FAILED:CNF-0061-probe1 sentinel absent")
        return 1
    errs = S.errors(doc)
    if errs:
        print("FAILED:CNF-0061-probe1 schema-invalid", errs[0])
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not S.errors(garbage):
            print("FAILED:CNF-0061-probe1 schema accepts garbage")
            return 1

    m = C.measure_all()
    fails = C.assert_detector_invariants(m)
    print(
        f"coverage_both={m['coverage_enabled_both_trade_runs']} "
        f"traced_before={m['before']['traced_events']} "
        f"traced_after={m['after']['traced_events']}"
    )
    if fails:
        print("FAILED:CNF-0061-probe1 detector invariants")
        for f in fails:
            print(" ", f)
        return 1

    trade = m["trade"]
    side = trade["percentage_side_by_side"]
    print(
        f"percent before={side['before']} after={side['after']} "
        f"unchanged={side['unchanged']}"
    )
    print("newly_uncovered " + " ".join(trade["newly_uncovered_file_lines"]))
    rep = S.payload(doc)
    if not rep.get("coverage_enabled_both_runs"):
        print("FAILED:CNF-0061-probe1 artifact coverage_enabled_both_runs false")
        return 1
    if rep.get("newly_uncovered_file_lines") != trade["newly_uncovered_file_lines"]:
        print("FAILED:CNF-0061-probe1 artifact newly_uncovered mismatch")
        print(" live", trade["newly_uncovered_file_lines"])
        print(" art ", rep.get("newly_uncovered_file_lines"))
        return 1
    art_side = rep.get("percentage_side_by_side") or {}
    if art_side.get("before") != side["before"] or art_side.get("after") != side["after"]:
        print("FAILED:CNF-0061-probe1 percentage mismatch", art_side, side)
        return 1
    if not art_side.get("unchanged"):
        print("FAILED:CNF-0061-probe1 artifact does not record unchanged percentage")
        return 1
    if not trade.get("coverage_moved_without_percentage_moving"):
        print("FAILED:CNF-0061-probe1 trade did not move lines at same percent")
        return 1
    sec = [r["file_line"] for r in trade["security_path_newly_uncovered"]]
    if not sec:
        print("FAILED:CNF-0061-probe1 no security-path newly uncovered lines")
        return 1
    if not (rep.get("security_or_rollback") or {}).get("any_hit"):
        print("FAILED:CNF-0061-probe1 artifact missed security/rollback hit")
        return 1

    thr = C.threshold_verdict(REPO)
    art_thr = rep.get("threshold_question") or {}
    if thr["verdict"] == "NOT-CHECKED":
        if art_thr.get("verdict") != "NOT-CHECKED":
            print("FAILED:CNF-0061-probe1 threshold absence folded into a pass")
            return 1
        print("threshold=NOT-CHECKED (no thresholds file)")
    elif art_thr.get("verdict") != thr["verdict"]:
        print("FAILED:CNF-0061-probe1 threshold verdict mismatch")
        return 1

    print("SUCCESS:CNF-0061-probe1 line-set delta with coverage enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
