"""Deterministic stagger/jitter arrival scheduler."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable

N_SCHEDULES = 1000
LARGE_N = 1000
MASTER_SEED = 20260826
WINDOW_TICKS = 10


@dataclass
class CampaignRow:
    rate_cap: int
    max_window: int
    n_units: int = 80
    max_observed_window_rate: float = 0.0


@dataclass
class Schedule:
    times_ticks: list[int]
    rate_cap: int = 0
    unit_ids: list[str] = field(default_factory=list)
    ceiling: int = 0
    window_ticks: int = WINDOW_TICKS


def max_sliding_window_count(times: Iterable[int], window: int) -> int:
    xs = sorted(int(t) for t in times)
    if not xs:
        return 0
    best = 0
    lo = 0
    for hi, t in enumerate(xs):
        while xs[lo] <= t - window:
            lo += 1
        best = max(best, hi - lo + 1)
    return best


def timestamps_identical(times: list[int]) -> bool:
    return len(times) > 1 and len(set(times)) == 1


def interarrival_all_equal(times: list[int]) -> bool:
    if len(times) < 3:
        return True
    deltas = [times[i] - times[i - 1] for i in range(1, len(times))]
    return len(set(deltas)) == 1


def schedule_arrivals(n: int, cap: int, seed: int = MASTER_SEED, jitter_frac: float = 0.0) -> Schedule:
    rng = random.Random(seed)
    times: list[int] = []
    t = 0
    for i in range(n):
        if jitter_frac > 0:
            t += 1 + rng.randint(0, max(1, int(2 * jitter_frac)))
        else:
            t += 1
        times.append(t)
    # Enforce cap by stretching if a window overshoots.
    while max_sliding_window_count(times, WINDOW_TICKS) > cap:
        times = [x * 2 for x in times]
        if jitter_frac > 0:
            times = [x + rng.randint(0, 1) for x in times]
            if len(set(times)) != n:
                times = [i * 2 + rng.randint(0, 1) for i in range(n)]
    return Schedule(
        times_ticks=times,
        rate_cap=cap,
        unit_ids=[f"U{i:04d}" for i in range(n)],
        ceiling=cap,
        window_ticks=WINDOW_TICKS,
    )


def naive_burst(n: int, cap: int) -> Schedule:
    return Schedule(
        times_ticks=[0] * n,
        rate_cap=cap,
        unit_ids=[f"U{i:04d}" for i in range(n)],
        ceiling=cap,
        window_ticks=WINDOW_TICKS,
    )


def run_property_campaign(n_schedules: int = N_SCHEDULES, seed: int = MASTER_SEED) -> list[CampaignRow]:
    rows: list[CampaignRow] = []
    caps = [4, 6, 8, 10, 12]
    for i in range(n_schedules):
        cap = caps[i % len(caps)]
        sched = schedule_arrivals(80, cap, seed=seed + i, jitter_frac=0.4 if i % 2 else 0.0)
        mx = max_sliding_window_count(sched.times_ticks, WINDOW_TICKS)
        rows.append(
            CampaignRow(
                rate_cap=cap,
                max_window=mx,
                n_units=80,
                max_observed_window_rate=mx / float(WINDOW_TICKS),
            )
        )
    return rows


def large_dispatch_rows() -> list[dict]:
    out = []
    for cap in (8, 10, 12):
        sched = schedule_arrivals(LARGE_N, cap, seed=MASTER_SEED + cap, jitter_frac=0.0)
        mx = max_sliding_window_count(sched.times_ticks, WINDOW_TICKS)
        out.append(
            {
                "n_units": LARGE_N,
                "rate_cap": cap,
                "max_window": mx,
                "max_observed_window_rate": mx / float(WINDOW_TICKS),
            }
        )
    return out
