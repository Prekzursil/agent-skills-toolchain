#!/usr/bin/env python3
"""Named probe 2: jitter is applied; stats reviewer re-derives the band.

Independent of probe1's printed summary: regenerates the same 1000-schedule
campaign from the recorded master seed, then computes quartiles from the
raw per-schedule max_window_count list. Burst twin (identical timestamps)
must exceed the cap. Zero-jitter stagger still respects the cap and has
constant deltas; jittered schedules do not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from arrival_scheduler.scheduler import (  # noqa: E402
    MASTER_SEED,
    N_SCHEDULES,
    WINDOW_TICKS,
    interarrival_all_equal,
    max_sliding_window_count,
    naive_burst,
    run_property_campaign,
    schedule_arrivals,
    timestamps_identical,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0092-probe2 {msg}")
    return 1


def linear_quartiles(xs: list[int] | list[float]) -> dict:
    """Re-derive q1/median/q3/iqr from the raw list (not from a summary)."""
    if not xs:
        raise ValueError("empty sample")
    ys = sorted(float(x) for x in xs)
    n = len(ys)

    def pct(p: float) -> float:
        if n == 1:
            return ys[0]
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return ys[lo] * (1.0 - frac) + ys[hi] * frac

    q1 = pct(0.25)
    median = pct(0.50)
    q3 = pct(0.75)
    return {
        "n": n,
        "min": ys[0],
        "q1": q1,
        "median": median,
        "q3": q3,
        "max": ys[-1],
        "iqr": q3 - q1,
        "method": "linear-interpolation-quartiles-on-raw-list",
    }


def main() -> int:
    rows = run_property_campaign()
    if len(rows) < 1000:
        return fail(f"n_schedules={len(rows)} want>={N_SCHEDULES}")
    raw = [r.max_window for r in rows]
    band = linear_quartiles(raw)
    util = [r.max_window / r.rate_cap for r in rows]
    util_band = linear_quartiles(util)
    if band["max"] > max(r.rate_cap for r in rows):
        return fail("band.max exceeded the largest cap in the campaign")
    exceeded = [r for r in rows if r.max_window > r.rate_cap]
    if exceeded:
        return fail(f"campaign exceeded cap: {exceeded[0]}")

    n = 80
    cap = 10
    jittered = schedule_arrivals(n, cap, seed=MASTER_SEED + 7, jitter_frac=1.0)
    zero = schedule_arrivals(n, cap, seed=MASTER_SEED + 7, jitter_frac=0.0)
    replay = schedule_arrivals(n, cap, seed=MASTER_SEED + 7, jitter_frac=1.0)
    other = schedule_arrivals(n, cap, seed=MASTER_SEED + 8, jitter_frac=1.0)
    burst = naive_burst(n, cap)

    if timestamps_identical(burst.times_ticks) is not True:
        return fail("burst twin must have identical timestamps")
    burst_max = max_sliding_window_count(burst.times_ticks, WINDOW_TICKS)
    if burst_max <= cap:
        return fail(f"burst max_window={burst_max} did not exceed cap={cap}")
    if timestamps_identical(jittered.times_ticks):
        return fail("jittered schedule has identical timestamps (defect)")
    if len(set(jittered.times_ticks)) != n:
        return fail("jittered timestamps are not unique")
    if interarrival_all_equal(zero.times_ticks) is not True:
        return fail("zero-jitter stagger must have constant inter-arrival")
    if interarrival_all_equal(jittered.times_ticks):
        return fail("jitter_frac>0 produced constant inter-arrival")
    if jittered.times_ticks != replay.times_ticks:
        return fail("same seed did not replay")
    if jittered.times_ticks == other.times_ticks:
        return fail("different seed produced an identical trace")
    if jittered.times_ticks == zero.times_ticks:
        return fail("jitter_frac did not change the timestamp vector")
    zero_max = max_sliding_window_count(zero.times_ticks, WINDOW_TICKS)
    if zero_max > cap:
        return fail(f"zero-jitter stagger exceeded cap max_window={zero_max}")

    payload = {
        "probe": "probe2-jitter-and-stats-reviewer",
        "unit_id": "TST-0092",
        "reviewer_id": "TST-0092-probe2-stats-and-jitter",
        "independent": True,
        "starts_from": "recorded master seed; raw max_window_count; not probe1 summary",
        "master_seed": MASTER_SEED,
        "n_schedules": len(rows),
        "variance_band_from_raw_max_window": band,
        "variance_band_from_raw_utilization": util_band,
        "jitter_applied": True,
        "identical_timestamps_is_defect": True,
        "burst_identical_timestamps": True,
        "burst_max_window": burst_max,
        "burst_exceeds_cap": burst_max > cap,
        "zero_jitter_constant_deltas": True,
        "jittered_unique_timestamps": True,
        "same_seed_replay": True,
        "different_seed_different_trace": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"iqr_raw={band['iqr']} median={band['median']} "
        f"burst_max={burst_max} jitter_unique={n}"
    )
    print(
        "SUCCESS:TST-0092-probe2 jitter applied; burst exceeds cap; "
        "IQR re-derived from raw max_window_count"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
