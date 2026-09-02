#!/usr/bin/env python3
"""Probe 2 (negative control): strip the recorded seed; reproducibility FAILS.

Both-states: with the seed recorded, two resolves match. With the seed
record removed, resolve raises MissingSeedRecord instead of picking the
first-listed option. An explicit list-order mutant still returns a winner,
so the control discriminates the production engine from implicit order.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import coin_flip_policy, exact_tie_fixture  # noqa: E402
from council.vote.tiebreak import (  # noqa: E402
    MissingSeedRecord,
    implicit_order_mutant_winner,
    permute_case,
    reproduce,
    resolve,
)


def main() -> int:
    case = exact_tie_fixture()
    recorded = coin_flip_policy()
    first = resolve(case, recorded)
    second = resolve(case, recorded)
    stripped = coin_flip_policy(seed=None)
    missing_raised = False
    missing_type = None
    try:
        resolve(case, stripped)
    except MissingSeedRecord as exc:
        missing_raised = True
        missing_type = type(exc).__name__

    reproduce_stripped = False
    try:
        reproduce_stripped = reproduce(case, stripped, first)
    except MissingSeedRecord:
        reproduce_stripped = False

    mutant_original = implicit_order_mutant_winner(case.options)
    mutant_reversed = implicit_order_mutant_winner(permute_case(case).options)

    ok = (
        first == second
        and first.seed_used == recorded.seed
        and missing_raised
        and reproduce_stripped is False
        and mutant_original == "alpha"
        and mutant_reversed == "beta"
        and mutant_original != mutant_reversed
    )
    payload = {
        "probe": "probe2-seed-removed",
        "unit_id": "IMP-0354",
        "with_seed": {
            "kind": first.kind,
            "winner": first.winner,
            "twice_identical": first == second,
            "seed_used": first.seed_used,
        },
        "seed_stripped": {
            "missing_seed_raised": missing_raised,
            "exception": missing_type,
            "reproduce_succeeded": reproduce_stripped,
        },
        "implicit_order_mutant": {
            "original_listing_winner": mutant_original,
            "reversed_listing_winner": mutant_reversed,
            "listing_order_changes_winner": mutant_original != mutant_reversed,
        },
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0354-probe2 seed-removed reproducibility")
        return 1
    print(
        "SUCCESS:IMP-0354-probe2 recorded seed replays; stripped seed fails; "
        "list-order mutant still picks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
