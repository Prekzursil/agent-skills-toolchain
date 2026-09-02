#!/usr/bin/env python3
"""Probe 2: reviewer re-runs the delete-one-test DETECTOR CONTROL."""
from __future__ import annotations

import json
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
        print("FAILED:CNF-0061-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0061-probe2 self-declared", doc.get("state"))
        return 1
    errs = S.errors(doc)
    if errs:
        print("FAILED:CNF-0061-probe2 schema-invalid", errs[0])
        return 1

    m = C.measure_all()
    control = m["control"]
    lost = control["newly_uncovered_file_lines"]
    print(
        f"deleted_test={m['deleted_test']} "
        f"coverage_enabled={m['coverage_enabled_both_control_runs']} "
        f"newly_uncovered_count={control['newly_uncovered_count']}"
    )
    print("control_uncovered " + " ".join(lost))
    if not m.get("coverage_enabled_both_control_runs"):
        print("FAILED:CNF-0061-probe2 control ran without coverage")
        return 1
    if control["newly_uncovered_count"] <= 0 or not lost:
        print("FAILED:CNF-0061-probe2 delete-one-test uncovered set empty")
        return 1
    if not any(x.startswith("rollback.py:") for x in lost):
        print("FAILED:CNF-0061-probe2 control did not hit rollback path")
        return 1

    rep = S.payload(doc)
    art_ctl = rep.get("detector_control") or {}
    if art_ctl.get("newly_uncovered_file_lines") != lost:
        print("FAILED:CNF-0061-probe2 artifact control mismatch")
        print(" live", lost)
        print(" art ", art_ctl.get("newly_uncovered_file_lines"))
        return 1
    if not art_ctl.get("non_empty") or int(art_ctl.get("newly_uncovered_count") or 0) < 1:
        print("FAILED:CNF-0061-probe2 artifact control not non-empty")
        return 1

    blind = m["without_coverage"]
    print(
        f"without_coverage enabled={m['without_coverage_full']['coverage_enabled']} "
        f"newly_uncovered_count={blind['newly_uncovered_count']}"
    )
    if m["without_coverage_full"].get("coverage_enabled"):
        print("FAILED:CNF-0061-probe2 no-coverage run was traced")
        return 1
    if int(blind.get("newly_uncovered_count") or 0) != 0:
        print("FAILED:CNF-0061-probe2 no-coverage run was not blind")
        return 1
    art_blind = rep.get("without_coverage_control") or {}
    if art_blind.get("coverage_enabled") is not False or not art_blind.get("blind"):
        print("FAILED:CNF-0061-probe2 artifact missing blindness control")
        return 1

    reviewer = doc.get("reviewer") or {}
    notes = str(reviewer.get("notes") or "")
    if not reviewer.get("independent") or not (
        rep.get("re_ran_detector_control") or "re-ran detector control" in notes
    ):
        print("FAILED:CNF-0061-probe2 reviewer did not re-run control")
        return 1

    print("SUCCESS:CNF-0061-probe2 delete-one-test control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
