#!/usr/bin/env python3
"""Named probe 1: round-robin ranking is order-independent across 20 shuffles.

Same judgements, twenty shuffled pairing schedules. Winner and ranking must
not move. A schedule-order tie-break would fail this test; Copeland+id must
not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.topology.tournament import (  # noqa: E402
    METHOD_ROUND_ROBIN,
    METHOD_SWISS,
    run_tournament,
    shuffle_trial,
    transitive_judgements,
)

MODULE = REPO / "tools" / "council" / "topology" / "tournament.py"
CONTESTANTS = ["alpha", "bravo", "charlie", "delta", "echo"]
N_SHUFFLES = 20


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0287-probe1 {msg}")
    return 1


def schedule_order_ranking(matches: list[dict]) -> list[str]:
    """Mutant: first contestant to reach a win, in match order. Order-dependent."""
    seen: list[str] = []
    for match in matches:
        w = match["winner"]
        if w not in seen:
            seen.append(w)
        loser = match["loser"]
        if loser not in seen:
            seen.append(loser)
    return seen


def main() -> int:
    if not MODULE.is_file() or MODULE.stat().st_size < 200:
        return fail("tools/council/topology/tournament.py missing")

    judgements = transitive_judgements(CONTESTANTS)
    trial = shuffle_trial(
        CONTESTANTS,
        judgements,
        n=N_SHUFFLES,
        method=METHOD_ROUND_ROBIN,
        base_seed=0,
    )
    if trial["n"] != N_SHUFFLES:
        return fail(f"n={trial['n']} want={N_SHUFFLES}")
    if not trial["order_independent"]:
        return fail(
            f"round-robin not order-independent winners={trial['unique_winners']} "
            f"ranking_count={trial['unique_ranking_count']}"
        )
    if trial["unique_winners"] != ["alpha"]:
        return fail(f"winner set {trial['unique_winners']} want ['alpha']")
    if trial["cycle_reported_any"]:
        return fail("transitive field reported a cycle")
    if not trial["order_independent_ranking"]:
        return fail("ranking moved under shuffle")

    base = run_tournament(CONTESTANTS, judgements, method=METHOD_ROUND_ROBIN, seed=0)
    if base.winner != "alpha" or base.condorcet_winner != "alpha":
        return fail(f"condorcet winner {base.condorcet_winner} want alpha")
    if base.ranking != CONTESTANTS:
        return fail(f"ranking {base.ranking} want {CONTESTANTS}")
    if base.scores != {"alpha": 4, "bravo": 3, "charlie": 2, "delta": 1, "echo": 0}:
        return fail(f"copeland scores {base.scores}")

    mutant_rankings = []
    for seed in range(N_SHUFFLES):
        out = run_tournament(CONTESTANTS, judgements, method=METHOD_ROUND_ROBIN, seed=seed)
        mutant_rankings.append(tuple(schedule_order_ranking(out.matches)))
    if len(set(mutant_rankings)) < 2:
        return fail("schedule-order mutant did not vary; probe cannot discriminate")

    swiss = shuffle_trial(
        CONTESTANTS,
        judgements,
        n=N_SHUFFLES,
        method=METHOD_SWISS,
        base_seed=0,
        swiss_rounds=2,
    )
    payload = {
        "unit_id": "IMP-0287",
        "probe": "probe1-order-independence",
        "pass": True,
        "n_shuffles": N_SHUFFLES,
        "method": METHOD_ROUND_ROBIN,
        "winners": trial["winners"],
        "unique_winners": trial["unique_winners"],
        "unique_ranking_count": trial["unique_ranking_count"],
        "order_independent": True,
        "condorcet_winner": base.condorcet_winner,
        "ranking": base.ranking,
        "scores": base.scores,
        "mutant_schedule_order_ranking_unique": len(set(mutant_rankings)),
        "swiss_incomplete_unique_winners": swiss["unique_winners"],
        "swiss_claimed_order_independent": False,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"shuffles={N_SHUFFLES} winner=alpha unique_rankings=1 "
        f"mutant_rankings={len(set(mutant_rankings))} "
        f"swiss_winners={swiss['unique_winners']}"
    )
    print("SUCCESS:IMP-0287-probe1 order independence across 20 shuffles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
