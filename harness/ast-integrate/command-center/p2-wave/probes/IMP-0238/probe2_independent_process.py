#!/usr/bin/env python3
"""Probe 2: reproduction is executed by an independent process, from the ledger.

Independence is asserted from recorded PIDs, not self-report. A same-pid
ledger row is rejected by the FLAGSHIP gate (negative control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[2] / "blueprints" / "engineering"
sys.path.insert(0, str(ENGINE))

from engine import (  # noqa: E402
    REPRODUCTION_NOT_INDEPENDENT,
    run_investigation,
)
from ledger import read_events  # noqa: E402


def main() -> int:
    live = run_investigation("noop-increment is the cause", reproduce=True)
    fake = run_investigation("noop-increment is the cause", fake_same_pid=True)

    events = read_events(Path(live.ledger_path))
    requested = [
        e
        for e in events
        if e.get("kind") == "reproduction_requested" and e.get("request_id") == live.request_id
    ]
    executed = [
        e
        for e in events
        if e.get("kind") == "reproduction_executed"
        and e.get("request_id") == live.request_id
        and e.get("observed_failure") is True
    ]

    print(
        json.dumps(
            {
                "live": {
                    "status": live.status,
                    "reason": live.reason,
                    "proposer_pid": live.proposer_pid,
                    "executor_pid": live.executor_pid,
                    "ledger_path": live.ledger_path,
                },
                "ledger": {
                    "requested_pid": requested[-1]["pid"] if requested else None,
                    "executed_pid": executed[-1]["pid"] if executed else None,
                    "executed_self_report": bool(executed and executed[-1].get("self_report")),
                },
                "fake_same_pid": {
                    "status": fake.status,
                    "reason": fake.reason,
                    "proposer_pid": fake.proposer_pid,
                    "executor_pid": fake.executor_pid,
                },
            },
            sort_keys=True,
        )
    )

    if live.status != "ACCEPTED":
        print(
            "FAILED:IMP-0238-probe2 live investigation not accepted "
            f"status={live.status} reason={live.reason}"
        )
        return 1
    if not requested or not executed:
        print("FAILED:IMP-0238-probe2 ledger missing request or execution rows")
        return 1
    req_pid = int(requested[-1]["pid"])
    exe_pid = int(executed[-1]["pid"])
    if req_pid == exe_pid:
        print(f"FAILED:IMP-0238-probe2 ledger PIDs are not independent req={req_pid} exe={exe_pid}")
        return 1
    if live.proposer_pid != req_pid or live.executor_pid != exe_pid:
        print("FAILED:IMP-0238-probe2 result PIDs do not match ledger")
        return 1
    if executed[-1].get("self_report"):
        print("FAILED:IMP-0238-probe2 live execution marked self_report")
        return 1
    if fake.status != "REJECTED" or fake.reason != REPRODUCTION_NOT_INDEPENDENT:
        print(
            "FAILED:IMP-0238-probe2 same-pid self-report not rejected "
            f"status={fake.status} reason={fake.reason}"
        )
        return 1
    print(f"independent=True req_pid={req_pid} exe_pid={exe_pid} same_pid_rejected=True")
    print("SUCCESS:IMP-0238-probe2 independent-process reproduction asserted from ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
