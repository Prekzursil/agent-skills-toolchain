#!/usr/bin/env python3
"""Probe 1: simulated pressure → warning + refuse; below threshold → proceed.

Independent signal (1) of the catalog evidence_requirement. Negative control
runs in the same process so a refuse-only stub cannot go green.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import make_guard  # noqa: E402
import pressure_guard as pg  # noqa: E402


def main() -> int:
    meter, guard = make_guard(0.99)
    guard.queue.enqueue(
        pg.WorkTicket(ticket_id="opt-pending", kind="prefetch", optional=True)
    )
    refused = guard.admit_new_work("new-session", optional=False)
    meter.set_ratio(0.10)
    allowed = guard.admit_new_work("new-session", optional=False, ticket_id="below")
    host = None
    try:
        if Path("/proc/meminfo").is_file():
            host = pg.LinuxCommitMeter().sample().as_dict()
    except Exception as exc:  # noqa: BLE001
        host = {"error": f"{type(exc).__name__}: {exc}"}

    ok = (
        refused.admitted is False
        and refused.band == "refuse"
        and bool(refused.warning)
        and bool(guard.sink.records())
        and allowed.admitted is True
        and allowed.band == "normal"
        and allowed.warning is None
        and "opt-pending" in refused.shed_ticket_ids
        and guard.process_actions_issued() == []
    )
    payload = {
        "probe": "probe1-refuse-under-pressure",
        "unit_id": "IMP-0066",
        "pass": ok,
        "refused": refused.as_dict(),
        "allowed_below_threshold": allowed.as_dict(),
        "negative_control_same_run": True,
        "warning_count": len(guard.sink.records()),
        "process_actions_issued": guard.process_actions_issued(),
        "host_commit_sample": host,
        "host_commit_is_not_the_injected_meter": True,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0066-probe1 refuse/warn/negative-control")
        return 1
    print(
        "SUCCESS:IMP-0066-probe1 warning+refuse under pressure; "
        "below-threshold proceeds"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
