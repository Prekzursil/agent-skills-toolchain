#!/usr/bin/env python3
"""Probe 2: mechanically independent detector controls (planted fixtures).

Re-derives ACCEPT/REJECT from the harness before reading the artifact's answers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gates import controls_pass, detector_controls  # noqa: E402
from harness import BUDGET_LIMIT, CASES  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0075-fusion-superiority.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0075-probe2 {msg}")
    return 1


def main() -> int:
    ctrl = detector_controls(CASES, BUDGET_LIMIT)
    if not controls_pass(ctrl):
        print(json.dumps(ctrl, indent=2, sort_keys=True)[:4000])
        return fail("controls did not all pass")

    checks = [
        ("good.pass", ctrl["good"]["pass"]),
        ("good.verdict_ACCEPT", ctrl["good"]["verdict"] == "ACCEPT"),
        ("stage_padded.REJECT", ctrl["stage_padded"]["verdict"] == "REJECT"),
        ("stage_padded.unearned-fusion", ctrl["stage_padded"]["classification"] == "unearned-fusion"),
        ("degraded.REJECT", ctrl["degraded"]["verdict"] == "REJECT"),
        ("regression.reported", ctrl["per_case_regression"]["regresses_on_any_case"]),
        ("regression.aggregate_still_up", ctrl["per_case_regression"]["outperforms_every_source"]),
        ("budget.REFUSED", ctrl["budget_asymmetric"]["verdict"] == "REFUSED"),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            return fail(name)

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = SC.report_body(doc)
    recorded = body.get("detector_controls") or {}
    for key in ("good", "stage_padded", "degraded", "per_case_regression", "budget_asymmetric"):
        if (recorded.get(key) or {}).get("pass") is not True:
            return fail(f"artifact control {key} not pass")
        if recorded[key].get("verdict") != ctrl[key]["verdict"]:
            return fail(f"artifact control {key} verdict drift")

    answers = body.get("answers") or {}
    if answers.get("merely_adds_stages") is not False:
        return fail("live subject marked merely_adds_stages")
    if answers.get("gate_verdict") != "ACCEPT":
        return fail("live subject not ACCEPT")
    tests = {t["id"]: t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "budget-parity",
        "per-case-regression",
        "stage-count-alongside-score",
        "detector-stage-padded",
        "detector-budget-asymmetric",
        "detector-degraded",
    ):
        if (tests.get(tid) or {}).get("result") != "PASS":
            return fail(f"test {tid}")

    print(
        json.dumps(
            {
                "probe": "probe2-detector-controls",
                "unit_id": "CNF-0075",
                "good": ctrl["good"]["verdict"],
                "stage_padded": ctrl["stage_padded"]["verdict"],
                "degraded": ctrl["degraded"]["verdict"],
                "budget_asymmetric": ctrl["budget_asymmetric"]["verdict"],
                "planted_regressions": len(ctrl["per_case_regression"]["regressions"]),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0075-probe2 detector controls fire on planted fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
