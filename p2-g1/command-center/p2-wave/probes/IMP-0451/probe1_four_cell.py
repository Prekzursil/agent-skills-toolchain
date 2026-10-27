#!/usr/bin/env python3
"""IMP-0451 probe1: the four-cell truth table (monitor alive/dead x work
active/idle). The production detector must return HEALTHY / NO_CHANGE_MONITOR
/ STALE_MONITOR / UNDECIDABLE - the dead x idle cell must stay UNDECIDABLE
(the hardest cell: no guessing either mixed-cell neighbour). mtime-sourced
observation must be refused as UNDECIDABLE, never a liveness signal."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MS_PY = REPO / "tools" / "command-center" / "monitor_states.py"

spec = importlib.util.spec_from_file_location("imp0451_monitor_states", MS_PY)
M = importlib.util.module_from_spec(spec)
sys.modules["imp0451_monitor_states"] = M
spec.loader.exec_module(M)


def fail(msg):
    print("FAILED:IMP-0451-probe1 " + str(msg))
    return 1


def main() -> int:
    live = M.four_cell_live()
    verdicts = live["verdicts"]

    for cell, want in M.EXPECTED_VERDICT.items():
        got = verdicts.get(cell)
        if got != want:
            return fail("cell %s: expected %s, got %s" % (cell, want, got))
    if live.get("any_guess"):
        return fail("a cell was guessed instead of decided/UNDECIDABLE")

    if not M.four_verdicts_distinct(verdicts):
        return fail("verdicts not distinct: %s" % json.dumps(verdicts))

    hardest = M.hardest_cell_undecidable(verdicts)
    if verdicts.get(M.CELL_DEAD_IDLE) != M.UNDECIDABLE:
        return fail("dead-idle cell did not stay UNDECIDABLE")
    if hardest.get("undecidable_ok") is False:
        return fail("hardest-cell check failed: %s" % json.dumps(hardest)[:200])

    mt = live.get("mtime_control") or {}
    if str(mt.get("verdict")) != M.UNDECIDABLE:
        return fail("mtime control not UNDECIDABLE: %s" % json.dumps(mt)[:200])
    if not live.get("mtime_forbidden_undecidable", True):
        return fail("mtime-sourced observation was used as a liveness signal")

    # (e) both-states evidence: the naive single-bit detectors demonstrably
    # misread the mixed cells - idle-read-as-dead (11316) and
    # dead-read-as-idle (11315) - which is why the matched pair exists.
    if M.naive_silence_is_dead(True, False) != M.STALE_MONITOR:
        return fail("naive silence-is-dead failed to demonstrate idle-read-as-dead on alive-idle")
    if M.naive_any_activity_is_alive(False, True) != M.HEALTHY:
        return fail("naive any-activity-is-alive failed to demonstrate dead-read-as-idle on dead-active")
    if not (live.get("idle_read_as_dead") and live.get("dead_read_as_idle")):
        return fail("live naive misread flags missing - naive controls vacuous")

    print(json.dumps({
        "probe": "probe1-four-cell",
        "unit_id": "IMP-0451",
        "verdicts": verdicts,
        "four_distinct": live["four_distinct"],
        "all_match": live["all_match"],
        "any_guess": live["any_guess"],
        "hardest_cell": M.CELL_DEAD_IDLE,
        "hardest_verdict": verdicts[M.CELL_DEAD_IDLE],
        "mtime_control_verdict": str(mt.get("verdict")),
        "naive_silence_is_dead_alive_idle": M.naive_silence_is_dead(True, False),
        "naive_any_activity_is_alive_dead_active": M.naive_any_activity_is_alive(False, True),
        "idle_read_as_dead": live.get("idle_read_as_dead"),
        "dead_read_as_idle": live.get("dead_read_as_idle"),
        "sources": {"monitor": "heartbeat-jsonl", "work": "byte-growth"},
        "sentinel": "SENTINEL:IMP-0451:MONITOR-STATES-DISTINGUISHED",
    }, indent=2))
    print("SUCCESS:IMP-0451-probe1 four cells distinct; dead-idle UNDECIDABLE; mtime refused; naive detectors demonstrably worse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
