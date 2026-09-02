#!/usr/bin/env python3
"""Named probe 1: sliding-window cap over >=1000 generated schedules.

Evidence: simulated dispatch of >=1000 units at several caps, with the
max observed window rate printed per cap. Distinct from TST-0093 (429
response); this probe is prevention.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from arrival_scheduler.scheduler import (  # noqa: E402
    LARGE_N,
    MASTER_SEED,
    N_SCHEDULES,
    large_dispatch_rows,
    run_property_campaign,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0092-probe1 {msg}")
    return 1


def main() -> int:
    rows = run_property_campaign()
    if len(rows) < 1000:
        return fail(f"n_schedules={len(rows)} want>={N_SCHEDULES}")
    exceeded = [r.__dict__ for r in rows if r.max_window > r.rate_cap]
    if exceeded:
        return fail(f"{len(exceeded)} schedules exceeded cap: {exceeded[0]}")

    per_cap_max: dict[int, int] = {}
    per_cap_n: dict[int, int] = defaultdict(int)
    raw_max_window = []
    for r in rows:
        raw_max_window.append(r.max_window)
        per_cap_n[r.rate_cap] += 1
        prev = per_cap_max.get(r.rate_cap, 0)
        if r.max_window > prev:
            per_cap_max[r.rate_cap] = r.max_window

    large = large_dispatch_rows()
    large_by_cap = {}
    for row in large:
        if row["n_units"] < 1000:
            return fail(f"large dispatch n={row['n_units']} < {LARGE_N}")
        if row["max_window"] > row["rate_cap"]:
            return fail(
                f"large dispatch cap={row['rate_cap']} max_window={row['max_window']}"
            )
        large_by_cap[str(row["rate_cap"])] = row["max_observed_window_rate"]

    # Printed evidence line: max observed window rate per cap (large dispatch).
    printed = " ".join(
        f"cap={row['rate_cap']} n={row['n_units']} max_window_rate={row['max_observed_window_rate']}"
        for row in large
    )

    payload = {
        "probe": "probe1-sliding-window-cap",
        "unit_id": "TST-0092",
        "master_seed": MASTER_SEED,
        "n_schedules": len(rows),
        "n_schedules_ge_1000": len(rows) >= 1000,
        "large_dispatch_n": LARGE_N,
        "per_cap_max_window_campaign": {str(k): per_cap_max[k] for k in sorted(per_cap_max)},
        "per_cap_schedule_count": {str(k): per_cap_n[k] for k in sorted(per_cap_n)},
        "large_dispatch_max_window_rate_per_cap": large_by_cap,
        "raw_max_window_count": raw_max_window,
        "any_exceeds_cap": False,
        "distinct_from": "TST-0093 (429 response, not prevention)",
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(printed)
    print(
        "SUCCESS:TST-0092-probe1 "
        f"schedules={len(rows)} large_n={LARGE_N} {printed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
