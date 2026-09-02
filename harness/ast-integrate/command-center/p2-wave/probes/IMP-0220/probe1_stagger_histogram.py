#!/usr/bin/env python3
"""Probe 1: 200-unit synthetic fan-out respects the configured stagger.

Histogram is measured from injected-clock admission timestamps, not read back
from the config. A rate-cap-only arm proves the token bucket is load-bearing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    N_UNITS,
    STAGGER_INTERVAL_S,
    UNIT_ID,
    WALL_BUDGET_S,
    forbid_wall_clock_in_scheduler,
    run_fanout,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    wall_hits = forbid_wall_clock_in_scheduler()
    if wall_hits:
        return fail(f"scheduler-reads-wall:{wall_hits}")

    run = run_fanout(stagger_enabled=True)
    hist = run["hist"]
    per_rail = 50
    want_gaps = N_UNITS - len(hist["gaps_by_rail"])

    if run["n"] != N_UNITS or hist["n_events"] != N_UNITS:
        return fail(f"cohort-size n={run['n']} events={hist['n_events']}")
    if hist["n_rails"] != 4:
        return fail(f"rails={hist['n_rails']} want=4")
    if any(len(v) != per_rail - 1 for v in hist["gaps_by_rail"].values()):
        sizes = {k: len(v) for k, v in hist["gaps_by_rail"].items()}
        return fail(f"per-rail-gap-counts {sizes}")
    if len(hist["all_gaps"]) != want_gaps:
        return fail(f"gap-count={len(hist['all_gaps'])} want={want_gaps}")
    if not run["matches_stagger"]:
        return fail(f"histogram-mismatch bins={hist['bins']}")
    if run["burst"]:
        return fail("stagger-on reported as burst")
    expected_span = (per_rail - 1) * STAGGER_INTERVAL_S
    if abs(hist["span"] - expected_span) > 1e-9:
        return fail(f"span={hist['span']} want={expected_span}")
    if abs(run["clock_now"] - expected_span) > 1e-9:
        return fail(f"clock_now={run['clock_now']} want={expected_span}")
    if run["wall_s"] >= WALL_BUDGET_S:
        return fail(f"wall-clock-used wall_s={run['wall_s']:.4f}")
    if not run["unknown_rail_named"]:
        return fail("unknown-rail did not raise named unknown-rail:<id>")
    if hist["unique_timestamps"] != per_rail:
        return fail(f"unique_timestamps={hist['unique_timestamps']} want={per_rail}")

    capped = run_fanout(
        stagger_enabled=False,
        n=20,
        rate_per_s=10.0,
        interval_s=STAGGER_INTERVAL_S,
    )
    cap_hist = capped["hist"]
    if capped["burst"]:
        return fail("rate-cap arm collapsed to a burst")
    cap_interval = 1.0 / 10.0
    if not all(abs(g - cap_interval) <= 1e-9 for g in cap_hist["all_gaps"]):
        return fail(f"rate-cap histogram {cap_hist['bins']}")

    out = {
        "probe": "probe1-stagger-histogram",
        "unit_id": UNIT_ID,
        "pass": True,
        "n": N_UNITS,
        "interval_s": STAGGER_INTERVAL_S,
        "bins": hist["bins"],
        "span": hist["span"],
        "unique_timestamps": hist["unique_timestamps"],
        "clock_now": run["clock_now"],
        "wall_s": run["wall_s"],
        "sleep_calls": run["sleep_calls"],
        "rate_cap_bins": cap_hist["bins"],
        "unknown_rail_named": True,
        "wall_clock_hits": wall_hits,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"SUCCESS:{UNIT_ID}-probe1 n={N_UNITS} bins={hist['bins']} "
        f"span={hist['span']} wall_s={run['wall_s']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
