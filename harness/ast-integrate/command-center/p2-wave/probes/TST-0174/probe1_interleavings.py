#!/usr/bin/env python3
"""Probe 1: 1,000 dual-process interleavings; every read is a complete entry."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    census = H.production_census()
    result = H.run_atomic_property(H.TRIALS)
    payload = {
        "probe": "probe1-interleavings",
        "unit_id": H.UNIT,
        "pass": bool(result.get("pass")),
        "trials": result.get("trials"),
        "winners": result.get("winners"),
        "partial_trials": result.get("partial_trials"),
        "leftover_trials": result.get("leftover_trials"),
        "total_partial_reads": result.get("total_partial_reads"),
        "total_reader_reads": result.get("total_reader_reads"),
        "failures": result.get("failures"),
        "production_cache_present": census["present"],
        "measured_layer": census["measured_layer"],
        "publish": census["publish"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not result.get("pass"):
        print(
            "FAILED:TST-0174-probe1 "
            f"partial_trials={result.get('partial_trials')} "
            f"leftover_trials={result.get('leftover_trials')} "
            f"failures={len(result.get('failures') or [])}"
        )
        return 1
    print(
        "SUCCESS:TST-0174-probe1 "
        f"trials={result.get('trials')} "
        f"partial_reads={result.get('total_partial_reads')} "
        f"winners={result.get('winners')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
