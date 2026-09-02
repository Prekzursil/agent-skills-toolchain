#!/usr/bin/env python3
"""Probe 2: process-table snapshot — every pre-existing pid stays live.

Independent signal (2), the load-bearing one. A guard can refuse new work
and still have signalled a shared service; this probe reads /proc and a TCP
health check, then greps the implementation for termination APIs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from scenario import make_guard, start_shared_service  # noqa: E402
import pressure_guard as pg  # noqa: E402
import termination_audit as audit  # noqa: E402

GUARD_SRC = REPO / "tools" / "plugin" / "pressure_guard.py"


def _read_proc_stat(pid: int) -> str | None:
    path = Path("/proc") / str(pid) / "stat"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def main() -> int:
    svc = start_shared_service()
    try:
        pid = svc.pid
        stat_before = _read_proc_stat(pid)
        table_before = pg.snapshot_pids()
        state_before = pg.pid_state(pid)
        health_before = svc.healthy()

        meter, guard = make_guard(0.99)
        # Record the shared-service pid on the ticket so a sloppy port could
        # have signalled it. This implementation must still leave it live.
        refused = guard.admit_new_work(
            "new-session", optional=False, holder_pid=pid
        )
        for _ in range(8):
            guard.admit_new_work("optional-prefetch", optional=True)

        stat_after = _read_proc_stat(pid)
        table_after = pg.snapshot_pids()
        state_after = pg.pid_state(pid)
        health_after = svc.healthy()
        still_in_table = pid in table_after and pid in table_before
        live = pg.pid_is_live(pid)

        grep = audit.audit_file(GUARD_SRC)
        ok = (
            refused.admitted is False
            and stat_before is not None
            and stat_after is not None
            and still_in_table
            and live
            and health_before
            and health_after
            and state_before not in {None, "Z", "X"}
            and state_after not in {None, "Z", "X"}
            and grep["clean"] is True
            and guard.process_actions_issued() == []
        )
        payload = {
            "probe": "probe2-process-table-survives",
            "unit_id": "IMP-0066",
            "pass": ok,
            "pid": pid,
            "port": svc.port,
            "stat_before": (stat_before or "")[:160],
            "stat_after": (stat_after or "")[:160],
            "state_before": state_before,
            "state_after": state_after,
            "in_proc_before": pid in table_before,
            "in_proc_after": pid in table_after,
            "health_before": health_before,
            "health_after": health_after,
            "pid_is_live": live,
            "table_size_before": len(table_before),
            "table_size_after": len(table_after),
            "admit": refused.as_dict(),
            "process_actions_issued": guard.process_actions_issued(),
            "reviewer_grep": {
                "path": "tools/plugin/pressure_guard.py",
                "clean": grep["clean"],
                "hit_count": len(grep["hits"]),
                "hits": grep["hits"],
            },
        }
        print(json.dumps(payload, sort_keys=True))
        if not ok:
            print("FAILED:IMP-0066-probe2 process-table or reviewer-grep")
            return 1
        print(
            "SUCCESS:IMP-0066-probe2 shared service still in /proc; "
            "health PONG; guard source has no termination API"
        )
        return 0
    finally:
        svc.close()


if __name__ == "__main__":
    raise SystemExit(main())
