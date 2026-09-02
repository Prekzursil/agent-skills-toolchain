#!/usr/bin/env python3
"""Probe 2: both-states control — stagger disabled reproduces a burst.

The same histogram function is applied to stagger-on and stagger-off arms.
If both arms look the same, the measurement cannot see the difference.
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
    histogram_matches_stagger,
    is_burst,
    run_fanout,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    on = run_fanout(stagger_enabled=True)
    off = run_fanout(stagger_enabled=False)

    if on["hist"]["n_events"] != N_UNITS or off["hist"]["n_events"] != N_UNITS:
        return fail("cohort-size")

    on_match = histogram_matches_stagger(on["hist"], STAGGER_INTERVAL_S)
    off_match = histogram_matches_stagger(off["hist"], STAGGER_INTERVAL_S)
    on_burst = is_burst(on["hist"])
    off_burst = is_burst(off["hist"])

    if not on_match:
        return fail(f"stagger-on histogram {on['hist']['bins']}")
    if on_burst:
        return fail("stagger-on is a burst; stagger is a no-op")
    if not off_burst:
        return fail(
            f"stagger-off did not burst span={off['hist']['span']} "
            f"unique={off['hist']['unique_timestamps']} bins={off['hist']['bins']}"
        )
    if off_match:
        return fail("stagger-off still matches stagger histogram (detector blind)")
    if on["hist"]["bins"] == off["hist"]["bins"]:
        return fail("both arms produced the same bins")
    if off["clock_now"] != 0.0 or off["sleep_calls"] != 0:
        return fail(
            f"stagger-off advanced clock now={off['clock_now']} "
            f"sleeps={off['sleep_calls']}"
        )
    if off["wall_s"] >= WALL_BUDGET_S or on["wall_s"] >= WALL_BUDGET_S:
        return fail(f"wall on={on['wall_s']:.4f} off={off['wall_s']:.4f}")
    if off["hist"]["span"] >= on["hist"]["span"]:
        return fail(
            f"burst span {off['hist']['span']} not < stagger span {on['hist']['span']}"
        )

    out = {
        "probe": "probe2-burst-control",
        "unit_id": UNIT_ID,
        "pass": True,
        "stagger_on": {
            "bins": on["hist"]["bins"],
            "span": on["hist"]["span"],
            "unique_timestamps": on["hist"]["unique_timestamps"],
            "matches_stagger": on_match,
            "burst": on_burst,
        },
        "stagger_off": {
            "bins": off["hist"]["bins"],
            "span": off["hist"]["span"],
            "unique_timestamps": off["hist"]["unique_timestamps"],
            "matches_stagger": off_match,
            "burst": off_burst,
        },
        "detector_sees_difference": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"SUCCESS:{UNIT_ID}-probe2 on_bins={on['hist']['bins']} "
        f"off_bins={off['hist']['bins']} burst_off={off_burst}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
