#!/usr/bin/env python3
"""IMP-0213 probe 1: sensitivity grid is not a constant function.

Acceptance: an input grid yields >=3 distinct recommendations. A wrapper that
always returns BUILD is shown to fail that same check (both-states control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from workflows.path_recommender import (  # noqa: E402
    Inputs,
    SCENARIOS,
    constant_mutant_winners,
    recommend,
    run_grid,
)


def main() -> int:
    grid = run_grid()
    distinct = grid["distinct_recommendations"]
    n = grid["n_distinct"]
    mutant = sorted(set(constant_mutant_winners(SCENARIOS, "BUILD")))

    print(
        json.dumps(
            {
                "probe": "probe1-sensitivity-grid",
                "unit_id": "IMP-0213",
                "n_scenarios": grid["n_scenarios"],
                "winners_in_order": grid["winners_in_order"],
                "distinct_recommendations": distinct,
                "n_distinct": n,
                "constant_BUILD_mutant_distinct": mutant,
            },
            indent=2,
            sort_keys=True,
        )
    )

    if n < 3:
        print(
            f"FAILED:IMP-0213-probe1 constant-function: n_distinct={n} want>=3 "
            f"winners={distinct}"
        )
        return 1
    if mutant != ["BUILD"]:
        print(f"FAILED:IMP-0213-probe1 mutant control did not stay BUILD: {mutant}")
        return 1
    if len(mutant) >= 3:
        print("FAILED:IMP-0213-probe1 mutant control is not constant (control inert)")
        return 1

    green = dict(
        next(
            inp.as_record()
            for name, inp in SCENARIOS
            if name.startswith("greenfield")
        )
    )
    base = recommend(Inputs(**green))["recommendation"]
    if base != "BUILD":
        print(f"FAILED:IMP-0213-probe1 greenfield control expected BUILD got {base}")
        return 1
    flipped = dict(green)
    flipped.update(
        {
            "incumbent_coverage": 950,
            "incumbent_quality": 920,
            "licence_risk": 50,
            "n_candidates": 1,
            "anti_rebuild_blocks_build": True,
            "quality_bar": 800,
            "repair_effort": 150,
        }
    )
    after = recommend(Inputs(**flipped))["recommendation"]
    if after == "BUILD":
        print(
            "FAILED:IMP-0213-probe1 one-factor flip still BUILD after planting a "
            f"high-quality incumbent: {after}"
        )
        return 1
    print(
        f"one_factor_flip greenfield BUILD -> planted-incumbent {after} "
        f"(mutant_distinct={len(mutant)} live_distinct={n})"
    )
    print(
        f"SUCCESS:IMP-0213-probe1 n_distinct={n} {distinct} "
        "constant-BUILD-mutant-detected one-factor-flip-ok"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
