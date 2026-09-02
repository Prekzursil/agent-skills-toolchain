#!/usr/bin/env python3
"""Probe 1: yield curves, 12-source fire vs ground truth, both-states.

Catalog tests:
  * Seeded corpus with 12 distinct sources -> detector fires only after
    marginal yield collapses; fire point reported against ground truth.
  * Both-states: a corpus still yielding new sources must NOT fire.
Evidence: yield curves for three true source counts (6, 12, 24).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.stopping.evidence_saturation import (  # noqa: E402
    DETECTOR_CONFIG,
    YIELD_FLOOR,
    experiment_both_states,
    experiment_three_corpora,
    slim_windows,
)


def main() -> int:
    three = experiment_three_corpora()
    both = experiment_both_states(seed=28312)
    n12 = three["curves"]["n12"]
    n6 = three["curves"]["n6"]
    n24 = three["curves"]["n24"]

    report = {
        "probe": "probe1-yield-and-both-states",
        "unit_id": "TST-0283",
        "yield_floor": YIELD_FLOOR,
        "window": DETECTOR_CONFIG.window,
        "three_corpora_passed": three["passed"],
        "both_states_passed": both["passed"],
        "n12": {
            "fired": n12["fired"],
            "fire_effort": n12["fire_effort"],
            "true_source_count": n12["true_source_count"],
            "discovered": n12["discovered_at_fire_or_end"],
            "undiscovered": n12["undiscovered_at_fire_or_end"],
            "coverage": n12["coverage_at_fire_or_end"],
            "last_new_effort": n12["last_new_effort"],
            "lag_after_last_new": n12["lag_after_last_new"],
            "collapsed_before_fire": n12["collapsed_before_fire"],
            "premature": n12["premature"],
            "fire_yield": n12["fire_yield"],
            "windows": slim_windows(n12["windows"]),
        },
        "n6_fire_effort": n6["fire_effort"],
        "n24_fire_effort": n24["fire_effort"],
        "both_states": {
            "finite_fired": both["planted_bad"]["fired"],
            "stream_fired": both["known_good"]["fired"],
            "discriminates": both["discriminates"],
            "padding_not_inflated": both["padding_not_inflated"],
            "naive_fires_on_stream": both["naive_counter"]["fires_on_still_yielding"],
            "verbatim_saturated": both["planted_bad"]["verbatim"],
            "verbatim_stream": both["known_good"]["verbatim"],
            "verbatim_padded": both["padded"]["verbatim"],
            "verbatim_naive": both["naive_counter"]["verbatim"],
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(both["planted_bad"]["verbatim"])
    print(both["known_good"]["verbatim"])
    print(both["padded"]["verbatim"])

    if not three["passed"]:
        print("FAILED:TST-0283-probe1 three-corpora yield curves")
        return 1
    if not n12["fired"]:
        print("FAILED:TST-0283-probe1 n=12 detector silent (uncontrolled silence)")
        return 1
    if n12["premature"] or not n12["collapsed_before_fire"]:
        print("FAILED:TST-0283-probe1 n=12 fired before yield collapsed")
        return 1
    if (n12["last_new_effort"] or 0) > (n12["fire_effort"] or 0):
        print("FAILED:TST-0283-probe1 fire precedes last new source")
        return 1
    if n12["true_source_count"] != 12:
        print("FAILED:TST-0283-probe1 ground-truth n is not 12")
        return 1
    if n12["coverage_at_fire_or_end"] < 0.75:
        print("FAILED:TST-0283-probe1 coverage at fire < 0.75 vs ground truth")
        return 1
    if both["known_good"]["fired"]:
        print("FAILED:TST-0283-probe1 still-yielding corpus fired")
        return 1
    if not both["discriminates"]:
        print("FAILED:TST-0283-probe1 detector silent in both states")
        return 1
    if not both["padding_not_inflated"]:
        print("FAILED:TST-0283-probe1 padded duplicates inflated yield")
        return 1
    if not both["naive_counter"]["silent_in_neither_state"]:
        print("FAILED:TST-0283-probe1 naive effort counter did not fire in both states")
        return 1
    if not both["passed"]:
        print("FAILED:TST-0283-probe1 both-states contract")
        return 1

    print(
        "SUCCESS:TST-0283-probe1 n12 fire_effort={fe} discovered={d}/12 "
        "stream_silent=True three_corpora=True".format(
            fe=n12["fire_effort"],
            d=n12["discovered_at_fire_or_end"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
