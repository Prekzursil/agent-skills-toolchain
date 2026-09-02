#!/usr/bin/env python3
"""Probe 1: planted no-op shapes are found; live census is emitted.

Required tests:
  test_census_finds_a_planted_assertionless_test
  test_census_finds_a_planted_unconditional_skip
  test_census_finds_a_planted_always_xfail
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from testinfra.test_noop_census import run_all  # noqa: E402


def main() -> int:
    result = run_all(REPO)
    payload = {
        "probe": "probe1-planted-shapes-and-live-census",
        "unit_id": "TST-0126",
        "pass": result["pass"],
        "tests": result["tests"],
        "live": result["live"],
        "planted": result["planted"],
        "files_scanned": result["files_scanned"],
        "parse_failures": result["parse_failures"],
        "method": result["method"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not result["pass"]:
        print("FAILED:TST-0126-probe1 planted shapes not recovered")
        return 1
    live = result["live"]
    print(
        "SUCCESS:TST-0126-probe1 planted three shapes found; "
        f"live assertionless={live['assertionless_count']} "
        f"skip={live['unconditional_skip_count']} "
        f"xfail={live['always_xfail_count']} "
        f"union={live['union_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
