#!/usr/bin/env python3
"""Probe 2: static audit of the enforcement point.

Mechanically different from probe 1: no sandbox execution. AST-walks
production hosts and the planted call-time gate. A permission set that is
only recorded in metadata is escaped by construction.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from audit import measure  # noqa: E402
from common import UNIT, dump_json  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    live = measure()
    payload = {
        "ok": True,
        "metadata_only": live["metadata_only"],
        "escaped_by_construction": live["escaped_by_construction"],
        "production_call_time_files": live["production_call_time_files"],
        "production_gate_files": live["production_gate_files"],
        "production_metadata_mentions": live["production_metadata_mentions"],
        "planted_detected": live["planted_detected"],
        "imp_0059_receipt_present": live["imp_0059_receipt_present"],
        "imp_0059_test_present": live["imp_0059_test_present"],
    }
    print(dump_json(payload), end="")
    if not live["planted_detected"]:
        return fail("planted call-time gate was not classified as call-time")
    if live["production_call_time_files"]:
        # Unexpected wiring is a finding, not a probe crash: still exit 0 after
        # recording. Only the planted control is required for probe health.
        pass
    if live["imp_0059_receipt_present"] and live["production_call_time_files"]:
        pass
    print(f"SUCCESS:{UNIT}-probe2 structural enforcement-point audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
