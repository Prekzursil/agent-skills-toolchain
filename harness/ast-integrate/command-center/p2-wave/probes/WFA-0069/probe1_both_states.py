#!/usr/bin/env python3
"""Probe 1: both-states control on the adoption smoke harness.

A good adopted workflow must PASS the smoke case. A deliberately broken copy
must FAIL the same smoke case. A candidate whose smoke case cannot be
constructed must be reclassified UNKNOWN-NEEDS-PROBE.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from controls import run_both_states  # noqa: E402
from smoke import reset_bounds  # noqa: E402


def main() -> int:
    reset_bounds()
    with tempfile.TemporaryDirectory(prefix="wfa0069-p1-") as tmp:
        result = run_both_states(Path(tmp))
    print(
        json.dumps(
            {
                "good_passed": result["good_passed"],
                "broken_copy_failed_same_smoke": result["broken_copy_failed_same_smoke"],
                "unconstructable_reclassified": result["unconstructable_reclassified"],
                "good_terminal": result["good"]["smoke_run"]["terminal"],
                "broken_terminal": result["broken"]["smoke_run"]["terminal"],
                "unconstructable_terminal": result["unconstructable"]["smoke_run"]["terminal"],
                "unconstructable_disposition": result["unconstructable_disposition"],
            },
            sort_keys=True,
        )
    )
    if not result["good_passed"]:
        print("FAILED:WFA-0069-probe1 good adopted workflow did not pass smoke")
        return 1
    if not result["broken_copy_failed_same_smoke"]:
        print("FAILED:WFA-0069-probe1 broken copy did not fail the same smoke case")
        return 1
    if not result["unconstructable_reclassified"]:
        print("FAILED:WFA-0069-probe1 unconstructable not reclassified UNKNOWN-NEEDS-PROBE")
        return 1
    print("SUCCESS:WFA-0069-probe1 both-states adoption smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
