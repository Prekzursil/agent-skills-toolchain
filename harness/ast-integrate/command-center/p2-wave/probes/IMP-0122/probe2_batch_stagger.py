#!/usr/bin/env python3
"""Named probe 2: 50-item batch stagger vs burst, measured server-side.

Signal (2) of IMP-0122. Negative control: the same client with stagger
disabled produces a burst histogram, proving the detector discriminates.
Also confirms jitter is not a fixed offset that re-synchronises the herd.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _lib import SENTINEL, TOOLS  # noqa: E402

sys.path.insert(0, str(TOOLS))
from marketplace.rate_limit_client import (  # noqa: E402
    measure_batch_histograms,
    measure_jitter_not_fixed_offset,
)


def main() -> int:
    hist = measure_batch_histograms(n=50, seed=11)
    jitter = measure_jitter_not_fixed_offset()
    slim = {
        "probe": "probe2-batch-stagger",
        "unit_id": "IMP-0122",
        "n": hist["n"],
        "discriminates": hist["discriminates"],
        "staggered": {
            k: hist["staggered"][k]
            for k in ("n", "span", "max_count", "burst_fraction", "occupied_bins")
        },
        "burst": {
            k: hist["burst"][k]
            for k in ("n", "span", "max_count", "burst_fraction", "occupied_bins")
        },
        "jitter": jitter,
    }
    print(json.dumps(slim, indent=2, sort_keys=True))
    if not hist["discriminates"]:
        print("FAILED:IMP-0122-probe2 histogram does not discriminate stagger vs burst")
        return 1
    if hist["burst"]["max_count"] != 50:
        print("FAILED:IMP-0122-probe2 unstaggered control is not a 50-wide burst")
        return 1
    if hist["staggered"]["span"] <= hist["burst"]["span"]:
        print("FAILED:IMP-0122-probe2 staggered span did not exceed burst span")
        return 1
    if not jitter["ok"]:
        print("FAILED:IMP-0122-probe2 jitter is a fixed offset")
        return 1
    print(
        f"staggered_burst_fraction={hist['staggered']['burst_fraction']} "
        f"burst_fraction={hist['burst']['burst_fraction']} "
        f"staggered_span={hist['staggered']['span']:.4f} "
        f"jitter_ok={jitter['ok']}"
    )
    print(f"{SENTINEL}-probe2 50-item stagger vs burst; jitter is not a fixed offset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
