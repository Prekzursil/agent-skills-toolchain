#!/usr/bin/env python3
"""Probe 2: skipped documented commands are NOT-CHECKED and never counted as passing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import doc_test as D  # noqa: E402

ART = REPO / "command-center/phase3/A8/TEST-PLAN.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0057-probe2 TEST-PLAN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = D.plan_payload(doc)
    tests = payload.get("documentation_command_tests") or {}
    rows = tests.get("rows") or []
    if not rows:
        print("FAILED:ARC-0057-probe2 no documentation_command_tests.rows")
        return 1

    live = D.product_report()
    ok, why = D.skip_accounting_holds(live)
    forged = D.forged_skip_as_pass_rejected(live)
    print(
        json.dumps(
            {
                "probe": "skip-accounting",
                "live_skipped": live["skipped"],
                "live_passed": live["passed"],
                "accounting_ok": ok,
                "accounting_why": why,
                "forged_skip_as_pass_rejected": forged,
            },
            sort_keys=True,
        )
    )
    if not ok:
        print(f"FAILED:ARC-0057-probe2 live skip accounting {why}")
        return 1
    if not forged:
        print("FAILED:ARC-0057-probe2 forged skip-as-pass was accepted")
        return 1

    skipped = [r for r in rows if r.get("verdict") == "NOT-CHECKED"]
    if not skipped:
        print("FAILED:ARC-0057-probe2 artifact has no NOT-CHECKED rows")
        return 1
    if any(r.get("counted_as_passing") for r in skipped):
        print("FAILED:ARC-0057-probe2 artifact counted a skip as passing")
        return 1
    if int(tests.get("passed") or -1) != sum(1 for r in rows if r.get("verdict") == "PASS"):
        print("FAILED:ARC-0057-probe2 artifact passed count includes non-PASS rows")
        return 1
    rec = payload.get("skip_accounting") or {}
    if rec.get("forged_skip_as_pass_rejected") is not True:
        print("FAILED:ARC-0057-probe2 artifact skip_accounting missing forge reject")
        return 1
    print("SUCCESS:ARC-0057-probe2 skip accounting NOT-CHECKED never passing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
