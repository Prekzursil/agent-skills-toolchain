#!/usr/bin/env python3
"""Named probe 2 (negative control): a constructed Condorcet cycle is reported.

Starts from the required tests, not the implementer summary. A rock-paper-
scissors field must set cycle_reported and must not mint a silent winner.
The same detector must stay quiet on a transitive field (both states).
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
    condorcet_cycle_judgements,
    run_tournament,
    shuffle_trial,
    transitive_judgements,
)

A, B, C = "rock", "paper", "scissors"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0287-probe2 {msg}")
    return 1


def silent_break(outcome) -> str:
    """Mutant: pick Copeland/lex leader and hide the cycle."""
    return outcome.ranking[0]


def main() -> int:
    cycle_j = condorcet_cycle_judgements(A, B, C)
    cycle = run_tournament([A, B, C], cycle_j, method=METHOD_ROUND_ROBIN, seed=7)
    if not cycle.cycle_reported:
        return fail("constructed cycle was not reported")
    if cycle.winner is not None or cycle.condorcet_winner is not None:
        return fail(f"cycle minted a silent winner {cycle.winner}")
    if cycle.stable_winner:
        return fail("cycle marked stable_winner=true")
    if sorted(cycle.cycles[0]) != sorted([A, B, C]):
        return fail(f"cycle members {cycle.cycles} want {[A, B, C]}")
    if cycle.scores != {A: 1, B: 1, C: 1}:
        return fail(f"cycle copeland {cycle.scores} want all 1")
    if "condorcet-cycle-reported" not in cycle.notes:
        return fail("cycle note missing")

    hidden = silent_break(cycle)
    if hidden not in {A, B, C}:
        return fail("mutant silent-break did not pick a contestant")
    if cycle.winner == hidden:
        return fail("module silently adopted Copeland/lex as the winner")

    trans_j = transitive_judgements(["alpha", "bravo", "charlie"])
    trans = run_tournament(
        ["alpha", "bravo", "charlie"], trans_j, method=METHOD_ROUND_ROBIN, seed=2
    )
    if trans.cycle_reported:
        return fail("transitive field reported a cycle")
    if trans.winner != "alpha" or not trans.stable_winner:
        return fail(f"transitive winner {trans.winner} want alpha")

    trial = shuffle_trial([A, B, C], cycle_j, n=20, method=METHOD_ROUND_ROBIN, base_seed=0)
    if not trial["cycle_reported_all"]:
        return fail("cycle not reported on every shuffle")
    if trial["stable_winner_any"]:
        return fail("a shuffle minted a stable winner on the cycle field")
    if trial["unique_winners"] != ["NONE"]:
        return fail(f"cycle winners {trial['unique_winners']} want ['NONE']")

    payload = {
        "unit_id": "IMP-0287",
        "probe": "probe2-condorcet-cycle",
        "pass": True,
        "reviewer_starts_from_tests": True,
        "cycle_reported": True,
        "cycle_members": cycle.cycles[0],
        "winner": cycle.winner,
        "stable_winner": False,
        "silent_break_would_pick": hidden,
        "silent_break_rejected": cycle.winner is None,
        "transitive_cycle_reported": False,
        "transitive_winner": trans.winner,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "shuffle_cycle_reported_all": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"cycle_reported=True winner=None silent_break={hidden} "
        f"transitive_winner=alpha fired_on_bad=True silent_on_good=True"
    )
    print("SUCCESS:IMP-0287-probe2 constructed Condorcet cycle reported not silently broken")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
