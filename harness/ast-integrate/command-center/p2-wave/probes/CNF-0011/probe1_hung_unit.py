#!/usr/bin/env python3
"""Probe 1: hung-unit injection must not globally barrier the cohort."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scheduler as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0011-scheduler-report.json"


def main() -> int:
    cfg = S.SchedulerConfig()
    jobs = S.load_cohort(REPO)["jobs"]
    result = S.run_scheduler(jobs, cfg, mode="configured")
    if len(result.terminals) != len(jobs):
        print(f"FAILED:CNF-0011-probe1 terminals={len(result.terminals)} jobs={len(jobs)}")
        return 1
    if any(r.blank or not r.terminal_state for r in result.terminals):
        print("FAILED:CNF-0011-probe1 blank terminal rows")
        return 1
    try:
        proof = S.hung_proof(result)
    except AssertionError as exc:
        print(f"FAILED:CNF-0011-probe1 {exc}")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0011-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    pay = S.artifact_payload(doc)
    inj = pay.get("hung_unit_injection") or {}
    if inj.get("global_barrier_refuted") is not True:
        print("FAILED:CNF-0011-probe1 artifact did not refute global barrier")
        return 1
    table = (pay.get("configured_run") or {}).get("terminal_state_table") or []
    if not table or any(row.get("blank") is not False for row in table):
        print("FAILED:CNF-0011-probe1 artifact terminal table has blanks")
        return 1
    if inj.get("injected_unit_id") != proof["injected_unit_id"]:
        print("FAILED:CNF-0011-probe1 hung id drift vs artifact")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-hung-unit",
                "pass": True,
                "hung": proof["injected_unit_id"],
                "survivors_before_timeout": proof["survivors_finished_before_hung_timeout"],
                "barrier_kind": proof["barrier_kind"],
                "blank_rows": 0,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0011-probe1 hung-unit injection surviving cohort completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
