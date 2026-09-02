#!/usr/bin/env python3
"""Probe 1: exhaustive small-profile search over methods x quorum x weights.

Mechanically: brute-force every other-seat ballot including ABSTAIN, compare the
focal seat's abstention outcome to the set of outcomes from real ballots. This is
not the validation-time API (probe 2) and not a preference-order no-show check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from enumerator import negative_control_hits, search_config, search_grid  # noqa: E402
from tally import ABSTAIN, QUORUM_FAIL, tally  # noqa: E402

PLANTED = {
    "method": "majority",
    "quorum": {"kind": "count", "min": 3},
    "weights": (1, 1, 1),
    "profile": ["A", "A", ABSTAIN],
}


def main() -> int:
    grid = search_grid()
    nc = grid["negative_control"]
    if nc["n_hits"] != 0:
        print("FAILED:TST-0269-probe1 enumerator-wrong-negative-control")
        print(json.dumps(nc, indent=2, sort_keys=True))
        return 1
    if nc["supermajority_n_hits"] != 0 or nc["unanimity_n_hits"] != 0:
        print("FAILED:TST-0269-probe1 extra-negative-control-nonzero")
        print(json.dumps(nc, indent=2, sort_keys=True))
        return 1
    if grid["n_vulnerable_configs"] < 1 or grid["n_advantage_profiles"] < 1:
        print("FAILED:TST-0269-probe1 vacuous-search")
        print(json.dumps({k: grid[k] for k in ("n_configs", "n_vulnerable_configs")}, indent=2))
        return 1

    planted_hits = search_config(
        PLANTED["method"], PLANTED["quorum"], PLANTED["weights"]
    )
    if not planted_hits:
        print("FAILED:TST-0269-probe1 planted-vulnerable-missed")
        return 1
    o_abs = tally(
        PLANTED["profile"],
        method=PLANTED["method"],
        weights=PLANTED["weights"],
        quorum=PLANTED["quorum"],
    )
    o_a = tally(
        ["A", "A", "A"],
        method=PLANTED["method"],
        weights=PLANTED["weights"],
        quorum=PLANTED["quorum"],
    )
    o_b = tally(
        ["A", "A", "B"],
        method=PLANTED["method"],
        weights=PLANTED["weights"],
        quorum=PLANTED["quorum"],
    )
    if o_abs != QUORUM_FAIL or o_a != "A" or o_b != "A":
        print("FAILED:TST-0269-probe1 planted-tally-mismatch", o_abs, o_a, o_b)
        return 1
    if o_abs in {o_a, o_b}:
        print("FAILED:TST-0269-probe1 planted-not-unique", o_abs, o_a, o_b)
        return 1

    triples = [
        {
            "method": t["method"],
            "quorum": t["quorum"],
            "weights": t["weights"],
            "n_profiles": t["n_profiles"],
            "demonstration": t["demonstration"],
        }
        for t in grid["triples"]
    ]
    summary = {
        "probe": "probe1-exhaustive-search",
        "unit_id": "TST-0269",
        "n_configs": grid["n_configs"],
        "n_vulnerable_configs": grid["n_vulnerable_configs"],
        "n_advantage_profiles": grid["n_advantage_profiles"],
        "negative_control_hits": nc["n_hits"],
        "planted_unique_by_abstention": True,
        "planted_outcome_abstain": o_abs,
        "planted_outcomes_by_ballot": {"A": o_a, "B": o_b},
        "triples_sample": triples[:8],
        "pass": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"vulnerable={grid['n_vulnerable_configs']}/{grid['n_configs']} "
        f"profiles={grid['n_advantage_profiles']} negative_control_hits={nc['n_hits']}"
    )
    print("SUCCESS:TST-0269-probe1 exhaustive search and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
