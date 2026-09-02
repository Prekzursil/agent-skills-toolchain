#!/usr/bin/env python3
"""Probe 1: kill+restart and uninterrupted both reconcile to zero UNKNOWNs.

Catalog tests_required[0]: both-states control — an uninterrupted run
reconciles to zero UNKNOWNs.

Evidence: (a) post-restart ledger recover() report, (b) remote job list
re-read from a second file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path[:] = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))

from scenario import canonical, scenario_kill_restart, scenario_uninterrupted  # noqa: E402

OUT = HERE / "probe1-both-states.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0150-probe1 {msg}")
    return 1


def main() -> int:
    killed = scenario_kill_restart()
    live = scenario_uninterrupted()
    krec = killed["reconcile"]
    lrec = live["reconcile"]
    payload = {
        "probe": "probe1-kill-restart-both-states",
        "unit_id": "TST-0150",
        "kill_restart": canonical(killed),
        "uninterrupted": canonical(live),
        "kill_harvested_during_recovery": killed.get("harvested_during_recovery"),
        "kill_failure_classes": killed.get("failure_classes"),
        "signals_kill": killed.get("signals_independent"),
        "signals_live": live.get("signals_independent"),
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))

    if not killed.get("monitor_dead_after_kill"):
        return fail("kill path did not raise MonitorDead after kill")
    if not killed.get("signals_independent", {}).get("independent"):
        return fail("kill path ledger and remote job list were not independent files")
    if not live.get("signals_independent", {}).get("independent"):
        return fail("uninterrupted ledger and remote job list were not independent files")
    if krec.get("unknown_count") != 0:
        return fail(f"kill+restart unknown_count={krec.get('unknown_count')} {krec.get('unknown_finished_ids')}")
    if lrec.get("unknown_count") != 0:
        return fail(f"uninterrupted unknown_count={lrec.get('unknown_count')} {lrec.get('unknown_finished_ids')}")
    if sorted(krec.get("remote_finished_ids") or []) != ["A", "B", "C"]:
        return fail(f"kill remote_finished {krec.get('remote_finished_ids')}")
    if sorted(lrec.get("remote_finished_ids") or []) != ["A", "B", "C"]:
        return fail(f"live remote_finished {lrec.get('remote_finished_ids')}")
    if sorted(krec.get("recovered_finished_ids") or []) != ["A", "B", "C"]:
        return fail(f"kill recovered {krec.get('recovered_finished_ids')}")
    if "D" in (krec.get("unknown_finished_ids") or []):
        return fail("in-flight D was marked UNKNOWN-finished")
    if sorted(killed.get("harvested_during_recovery") or []) != ["A", "B"]:
        return fail(f"expected recover to harvest A,B got {killed.get('harvested_during_recovery')}")
    if "monitor-dies-while-remote-work-continues" not in (killed.get("failure_classes") or []):
        return fail(f"failure class missing: {killed.get('failure_classes')}")
    if "D" not in (killed.get("in_flight_ids") or []):
        return fail("D was not left in-flight after restart")

    print(
        "SUCCESS:TST-0150-probe1 kill+restart unknown=0 uninterrupted unknown=0 "
        f"recovered={krec.get('recovered_finished_ids')} in_flight={killed.get('in_flight_ids')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
