#!/usr/bin/env python3
"""Probe 1: both-states control + boundary at limit-1, limit, limit+1.

Signal (a): the pre-flight check's rejection (message names the budget,
writer reports preflight_rejected, zero bytes_written / open / mkdir).
In-budget paths write and round-trip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from writer import DEFAULT_BUDGET  # noqa: E402


def main() -> int:
    doc = S.run_all(DEFAULT_BUDGET)
    v = S.verdicts(doc)
    required = (
        "limit_minus_1_writes",
        "limit_writes",
        "limit_plus_1_rejects",
        "mixed_all_or_nothing",
        "ghost_not_created",
    )
    print(json.dumps({"budget": doc["budget"], "host": doc["host"], "verdicts": v}, indent=2))
    b = doc["boundary"]
    print(
        "lengths "
        f"limit-1={b['limit_minus_1']['measured_len']} "
        f"limit={b['limit']['measured_len']} "
        f"limit+1={b['limit_plus_1']['measured_len']}"
    )
    print(
        "preflight "
        f"rejected={b['limit_plus_1']['preflight_rejected']} "
        f"bytes={b['limit_plus_1']['bytes_written']} "
        f"entries={b['limit_plus_1']['new_entries']}"
    )
    print("message=" + (b["limit_plus_1"]["message"] or ""))
    for name in required:
        if not v.get(name):
            print(f"FAILED:TST-0201-probe1 {name}")
            return 1
    print("SUCCESS:TST-0201-probe1 boundary both-states preflight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
