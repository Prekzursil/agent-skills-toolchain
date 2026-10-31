#!/usr/bin/env python3
"""TST-0283 probe 1: yield curves vs ground truth + both-states control.

T1: on a seeded 12-source corpus the detector fires ONLY after the marginal
yield collapses (fire point after the last new source, 12/12 discovered at
fire, coverage 1.0 reported against ground truth). T2: a still-yielding
stream (new independent source every draw) must NOT fire. Yield curves for
three corpora (6/12/24 true sources) report fire point vs ground truth, and
the naive effort-counter control fires on BOTH states (proving the detector
measures yield, not effort).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from council.stopping.evidence_saturation import (  # noqa: E402
    experiment_both_states,
    experiment_three_corpora,
)

FIRE_LAG_FLOOR = 8  # at least one full window of collapsed yield before firing


def main() -> int:
    checks: dict[str, bool] = {}
    three = experiment_three_corpora(seed=28312)
    checks["three_corpora_all_fire_at_full_coverage"] = three["passed"]
    for name, c in three["curves"].items():
        checks[f"{name}_coverage_1"] = c["coverage_at_fire"] == 1.0
        checks[f"{name}_fire_after_collapse"] = (
            c["fire_effort"] > c["true_source_count"]
        )

    bs = experiment_both_states(seed=28312, effort=400)
    checks["saturated_fires"] = bs["saturated"]["fired"]
    checks["saturated_discovers_all"] = bs["saturated"]["coverage_at_fire"] == 1.0
    checks["saturated_fire_after_collapse"] = (
        bs["saturated"]["fire_effort"] - 12 >= FIRE_LAG_FLOOR
    )
    checks["still_yielding_silent"] = bs["still_yielding"]["fired"] is False
    checks["still_yielding_discovers_all_draws"] = (
        bs["still_yielding"]["discovered"] == 400
    )
    checks["naive_counter_fires_on_both"] = (
        bs["naive_counter"]["fires_on_saturated"]
        and bs["naive_counter"]["fires_on_still_yielding"]
    )
    checks["detector_discriminates"] = bs["discriminates"]

    out = {
        "probe": "probe1_yield_and_both_states",
        "unit": "TST-0283",
        "yield_curves": three["curves"],
        "both_states": bs,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-yield.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True)[:2000])
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
