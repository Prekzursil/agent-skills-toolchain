#!/usr/bin/env python3
"""Named probe 2: static audit, negative control, independent reviewer, hook syntax.

Signal 1: AST audit of fail-closed sources (no swallow-to-pass), both-states on the auditor.
Signal 2: flipping hooks to fail-closed turns the injection predicate red; independent
kind-classifier agrees with the table without reading posture; hooks fail-open on
invalid JSON config.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
sys.path.insert(0, str(REPO))

import failure_policy as FP  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0053.json"


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:IMP-0053-probe2 receipt missing")
        return 1
    rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if rec.get("unit_id") != "IMP-0053":
        print("FAILED:IMP-0053-probe2 unit_id", rec.get("unit_id"))
        return 1

    table = FP.load_table()
    audit = FP.audit_fail_closed_components(table)
    if not audit["clean"]:
        print("FAILED:IMP-0053-probe2 static audit", audit["findings"])
        return 1
    both = FP.both_states_auditor()
    if not both["both_states"]:
        print("FAILED:IMP-0053-probe2 auditor both-states", both)
        return 1
    control = FP.negative_control_flip_goes_red("hooks", table)
    if not control["went_red"]:
        print("FAILED:IMP-0053-probe2 negative control did not go red")
        return 1
    review = FP.independent_classification(table)
    if review["verdict"] != "PASS" or review["reads_posture_field"]:
        print("FAILED:IMP-0053-probe2 reviewer", review)
        return 1
    syntax = FP.hooks_config_syntax_error()
    if not (syntax.proceed and syntax.failure and syntax.degraded):
        print("FAILED:IMP-0053-probe2 hooks syntax was not fail-open", syntax)
        return 1

    report = {
        "probe": "probe2-audit-and-controls",
        "unit_id": "IMP-0053",
        "static_audit_clean": True,
        "auditor_both_states": True,
        "negative_control_went_red": True,
        "reviewer_verdict": review["verdict"],
        "hooks_syntax_fail_open": True,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "audit_clean=True both_states=True went_red=True "
        f"reviewer={review['verdict']} hooks_syntax_fail_open=True"
    )
    print("SUCCESS:IMP-0053-probe2 static audit, negative control, reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
