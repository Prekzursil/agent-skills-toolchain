#!/usr/bin/env python3
"""Probe 2: staleness window refuses a write; clean stamp within the window permits.

Independent reviewer path: re-runs the gate and the report writer, plus reserved
device-name prefix and unreadable-path-never-skipped controls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    WINDOW,
    reserved_prefix_probe,
    run_clean,
    run_staleness,
    run_unreadable_not_skipped,
    sandbox,
)


def fail(reason: str) -> int:
    print(f"FAILED:SYN-0019-probe2 {reason}")
    return 1


def main() -> int:
    with sandbox("syn0019-p2-clean-") as clean_root:
        clean = run_clean(clean_root, window=WINDOW)
    with sandbox("syn0019-p2-stale-") as stale_root:
        stale = run_staleness(stale_root, window=WINDOW)
    with sandbox("syn0019-p2-unread-") as unread_root:
        unread = run_unreadable_not_skipped(unread_root)
    reserved = reserved_prefix_probe()

    gap = float(stale.get("wall_clock_gap_seconds") or 0)
    ok = (
        clean["verdict"] == "PERMITTED"
        and clean["exit_code"] == 0
        and clean["wrote"] is True
        and float(clean.get("wall_clock_gap_seconds") or 0) <= WINDOW
        and stale["verification_verdict"] == "PERMITTED"
        and int(stale.get("verification_exit_code")) == 0
        and stale["verdict"] == "BLOCKED"
        and stale["exit_code"] != 0
        and stale["wrote"] is False
        and stale["output_exists"] is False
        and "decayed-green" in (stale.get("blocking_conditions") or [])
        and gap > WINDOW
        and unread["path_in_table"] is True
        and unread["failed_never_skipped"] is True
        and unread["verdict"] == "BLOCKED"
        and "unreadable-path" in (unread.get("blocking_conditions") or [])
        and reserved["reserved_nul"]
        and reserved["reserved_nul_txt"]
        and reserved["reserved_com1"]
        and reserved["not_reserved"]
        and reserved["extended_prefix"]
        and reserved["windows_stat_target"]
        and reserved["linux_stat_target_unchanged"]
    )
    payload = {
        "probe": "probe2-staleness-and-clean",
        "unit_id": "SYN-0019",
        "pass": ok,
        "freshness_window_seconds": WINDOW,
        "clean": {
            "verdict": clean["verdict"],
            "exit_code": clean["exit_code"],
            "wrote": clean["wrote"],
            "timestamp": clean["timestamp"],
            "wall_clock_gap_seconds": clean.get("wall_clock_gap_seconds"),
        },
        "staleness": {
            "verification_verdict": stale.get("verification_verdict"),
            "write_verdict": stale["verdict"],
            "exit_code": stale["exit_code"],
            "wrote": stale["wrote"],
            "timestamp": stale["timestamp"],
            "wall_clock_gap_seconds": stale.get("wall_clock_gap_seconds"),
            "blocking_conditions": stale.get("blocking_conditions"),
        },
        "unreadable_never_skipped": unread,
        "reserved_device_names": reserved,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        return fail(
            "stale-PERMITTED-stamp-must-not-authorise-write; "
            "clean-within-window-must-PERMITTED; unreadable-never-skipped"
        )
    print(
        "SUCCESS:SYN-0019-probe2 staleness BLOCKED (decayed-green), "
        "clean PERMITTED exit 0, unreadable path kept in table"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
