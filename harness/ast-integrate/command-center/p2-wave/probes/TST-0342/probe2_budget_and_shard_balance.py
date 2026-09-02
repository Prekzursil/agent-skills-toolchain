#!/usr/bin/env python3
"""Probe 2: suite budget from a full run; shards packed by measured duration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_timeout_budget import (  # noqa: E402
    test_budget_measured_on_full_run_not_subset,
    test_shard_balance_from_measured_durations,
)


def main() -> int:
    budget = test_budget_measured_on_full_run_not_subset()
    shards = test_shard_balance_from_measured_durations()
    ok = budget["pass"] and shards["pass"]
    payload = {
        "probe": "probe2-budget-and-shard-balance",
        "unit_id": "TST-0342",
        "pass": ok,
        "test_budget_measured_on_full_run_not_subset": budget,
        "test_shard_balance_from_measured_durations": shards,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not ok:
        print("FAILED:TST-0342-probe2 budget source or shard balance")
        return 1
    print(
        f"budget_source={budget['budget_source']} "
        f"wall={budget['wall_clock_s']:.3f}s "
        f"subset={budget['subset_estimate_s']:.3f}s "
        f"dur_ratio={shards['shards_by_duration']['max_min_ratio']:.3f} "
        f"file_ratio={shards['shards_by_file_count']['max_min_ratio']:.3f}"
    )
    print(
        "SUCCESS:TST-0342-probe2 full-run budget; duration shards under "
        "declared ratio; file/test-count packing is a finding"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
