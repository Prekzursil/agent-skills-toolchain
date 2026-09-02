#!/usr/bin/env python3
"""Probe 1: live kill-and-resume plus idempotent replay; artifact must agree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0443.json"
SENTINEL = "SENTINEL:IMP-0443:LEDGER-RESUME-IDEMPOTENT"
QUESTION = (
    "Implement the append-only run ledger so an interrupted program resumes "
    "without re-running completed units and without double-counting. Exact "
    "question: after killing the runner at 60 percent and resuming, is the "
    "total set of executed units exactly the catalog with no unit executed twice?"
)


def main() -> int:
    report = S.run_suite()
    kill60 = report["kill60"]
    print(
        "kill60_ok="
        f"{kill60['ok']} before={kill60['before']['completed_count']} "
        f"after_n={len(kill60['executed_multiset_after'])} "
        f"dups={kill60['duplicates']} coverage={kill60['catalog_coverage_after']}"
    )
    print(f"replay_ok={report['replay']['ok']} all_kills_ok={report['all_kills_ok']}")
    if not report["all_kills_ok"]:
        print("FAILED:IMP-0443-probe1 a kill-and-resume trace did not cover the catalog")
        return 1
    if not kill60["ok"]:
        print("FAILED:IMP-0443-probe1 kill-at-60 did not resume to exact catalog")
        return 1
    if kill60["duplicates"]:
        print(f"FAILED:IMP-0443-probe1 duplicates={kill60['duplicates']}")
        return 1
    if not report["replay"]["ok"]:
        print("FAILED:IMP-0443-probe1 idempotent replay appended extra records")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0443-probe1 run-ledger artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0443-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0443-probe1 sentinel absent")
        return 1
    answer = doc.get("answer") or {}
    if answer.get("after_kill_at_60_and_resume_executed_set_equals_catalog") is not True:
        print("FAILED:IMP-0443-probe1 artifact answer is not true")
        return 1
    if answer.get("any_unit_executed_twice") is not False:
        print("FAILED:IMP-0443-probe1 artifact reports a duplicate execution")
        return 1
    if QUESTION not in text and doc.get("question") != QUESTION:
        # artifact must record the catalog question
        if "killing the runner at 60 percent" not in str(doc.get("question") or ""):
            print("FAILED:IMP-0443-probe1 catalog question absent from artifact")
            return 1
    print("SUCCESS:IMP-0443-probe1 kill-resume exact catalog no duplicates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
