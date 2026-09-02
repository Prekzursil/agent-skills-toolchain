#!/usr/bin/env python3
"""Probe 1: estate measurement — independent steps hidden by fail-fast."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
from aggregate import run_job  # noqa: E402

UNIT = "TST-0016"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    estate = C.measure_estate()
    targets = {w["file"]: w for w in estate.get("target_workflows") or []}
    q = targets.get(".github/workflows/quality.yml")
    n = targets.get(".github/workflows/no-runtime-junk.yml")
    print(f"source={estate.get('source')} live_yaml={estate.get('live_yaml_present')}")
    if q is None or n is None:
        return fail("target workflows missing from classification")

    q_hidden = int(q["independent_behind_failfast"])
    n_hidden = int(n["independent_behind_failfast"])
    print(
        f"quality.yml hidden={q_hidden} checks={q['independent_checks_behind_failfast']} "
        f"steps={q['step_count']}"
    )
    print(
        f"no-runtime-junk.yml hidden={n_hidden} "
        f"checks={n['independent_checks_behind_failfast']} steps={n['step_count']}"
    )
    if q_hidden < 1:
        return fail("quality.yml reported zero independent-behind-failfast steps")
    if n_hidden < 1:
        return fail("no-runtime-junk.yml reported zero independent-behind-failfast steps")

    tp = next((j for j in q["jobs"] if j.get("job_id") == "test-python"), None)
    lint = next((j for j in q["jobs"] if j.get("job_id") == "lint"), None)
    junk = next((j for j in n["jobs"] if j.get("job_id") == "no-runtime-junk"), None)
    if tp is None or lint is None or junk is None:
        return fail("expected jobs missing")
    print(
        f"test-python hidden={tp['independent_behind_failfast']} "
        f"checks={tp['independent_checks_behind_failfast']} steps={tp['step_count']}"
    )
    if int(tp["independent_checks_behind_failfast"]) < 40:
        return fail("test-python did not expose a large independent-check stack")

    from classify import specs_for_job

    lint_ff = run_job(specs_for_job(lint), "fail_fast")
    lint_ag = run_job(specs_for_job(lint), "aggregate")
    tp_ff = run_job(specs_for_job(tp), "fail_fast")
    tp_ag = run_job(specs_for_job(tp), "aggregate")
    junk_ff = run_job(specs_for_job(junk), "fail_fast")
    junk_ag = run_job(specs_for_job(junk), "aggregate")

    print(
        f"lint fail_fast_defects={len(lint_ff.defects)} "
        f"aggregate_defects={len(lint_ag.defects)} "
        f"ag_exit={lint_ag.exit_code}"
    )
    print(
        f"test-python fail_fast_defects={len(tp_ff.defects)} "
        f"aggregate_defects={len(tp_ag.defects)} "
        f"skipped_ff={len(tp_ff.skipped_fail_fast())}"
    )
    print(
        f"junk fail_fast_defects={len(junk_ff.defects)} "
        f"aggregate_defects={len(junk_ag.defects)}"
    )

    if len(lint_ff.defects) < 1:
        return fail("lint fail-fast reported no defects")
    if len(lint_ag.defects) <= len(lint_ff.defects):
        return fail("lint aggregator did not reveal hidden defects")
    if len(tp_ff.defects) != 1:
        return fail(f"test-python fail-fast should report 1, got {len(tp_ff.defects)}")
    if len(tp_ag.defects) < 40:
        return fail("test-python aggregator hid most independent checks")
    if tp_ag.exit_code != 1:
        return fail("test-python aggregate exit was not red")
    if len(junk_ag.defects) < 2:
        return fail("no-runtime-junk aggregator did not run both independent checks")
    if len(junk_ff.defects) != 1:
        return fail("no-runtime-junk fail-fast should hide the second check")

    payload = {
        "probe": "probe1-estate-hidden",
        "unit_id": UNIT,
        "source": estate.get("source"),
        "answer_per_workflow": estate.get("answer_per_workflow"),
        "lint_fail_fast_defects": len(lint_ff.defects),
        "lint_aggregate_defects": len(lint_ag.defects),
        "test_python_fail_fast_defects": len(tp_ff.defects),
        "test_python_aggregate_defects": len(tp_ag.defects),
        "junk_fail_fast_defects": len(junk_ff.defects),
        "junk_aggregate_defects": len(junk_ag.defects),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0016-probe1 independent checks hidden by fail-fast; "
        "aggregator reveals the full set"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
