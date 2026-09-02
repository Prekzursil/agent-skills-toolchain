#!/usr/bin/env python3
"""Probe 2: independent filesystem scan + os-level create trace.

Signal (b): a directory listing of the target root after a budget breach
shows no created entries. Process-level os.open/os.mkdir wrappers (not the
writer's own counters) record zero creates. The late-check writer is the
detector control: the same mixed package leaves residue and traced creates.
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
        "trace_breach_zero_creates",
        "trace_naive_creates",
        "naive_leaves_residue",
        "mixed_all_or_nothing",
        "limit_plus_1_rejects",
    )
    payload = {
        "budget": doc["budget"],
        "host": doc["host"],
        "scan_breach_entries": doc["traced_breach"]["entries_after"],
        "scan_breach_trace_creates": doc["traced_breach"]["trace_create_count"],
        "scan_naive_entries": doc["traced_naive"]["entries_after"],
        "scan_naive_trace_creates": doc["traced_naive"]["trace_create_count"],
        "naive_residue": doc["naive"]["residue"],
        "verdicts": v,
    }
    print(json.dumps(payload, indent=2))
    print(
        "scan "
        f"breach_entries={doc['traced_breach']['entries_after']} "
        f"breach_creates={doc['traced_breach']['trace_create_count']} "
        f"naive_residue={doc['naive']['residue']} "
        f"naive_creates={doc['traced_naive']['trace_create_count']}"
    )
    for name in required:
        if not v.get(name):
            print(f"FAILED:TST-0201-probe2 {name}")
            return 1
    print("SUCCESS:TST-0201-probe2 scan-and-trace detector-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
