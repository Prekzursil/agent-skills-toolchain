#!/usr/bin/env python3
"""Probe 1: Condorcet-cycle detection.

A constructed A>B>C / B>C>A / C>A>B profile must be REPORTED as a cycle.
The tie-break may emit a total order but must not set condorcet_winner and
must not claim the cycle was silently broken. The transitive control must
produce a unique Condorcet winner and an empty cycle list (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import aggregate as A  # noqa: E402
import fixtures as F  # noqa: E402
import recompute as R  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0070-probe1 {msg}")
    return 1


def main() -> int:
    rubric = F.default_rubric()
    cycle_doc = F.cycle_scorecards()
    cyc = A.aggregate(cycle_doc, rubric, REPO)
    members = [tuple(x["members"]) for x in cyc["cycles"]]
    print(
        json.dumps(
            {
                "cycle_condorcet_winner": cyc["condorcet_winner"],
                "cycle_count": len(cyc["cycles"]),
                "cycle_members": [list(m) for m in members],
                "cycle_ranking": [r["entry_id"] for r in cyc["ranking"]],
                "cycle_silently_broken": cyc["cycle_silently_broken"],
                "tie_break_applied": cyc["tie_break_applied"],
            },
            sort_keys=True,
        )
    )
    if cyc["cycle_silently_broken"] is not False:
        return fail("cycle_silently_broken must be false")
    if cyc["condorcet_winner"] is not None:
        return fail(f"cycle profile elected {cyc['condorcet_winner']}")
    if not cyc["cycles"]:
        return fail("cycle profile produced empty cycles (silent break)")
    wanted = {"CX", "CY", "CZ"}
    if not any(set(m) == wanted for m in members):
        return fail(f"expected cycle over {sorted(wanted)} got {members}")
    if not cyc["tie_break_applied"]:
        return fail("tie-break must be applied when no Condorcet winner exists")
    if len(cyc["ranking"]) != 3:
        return fail("cycle profile must still emit a declared total order")

    # Independent matrix recompute must also see the cycle (not hide it).
    ind = R.rank_from_matrix(
        cyc["pairwise_matrix"],
        cyc["entries"],
        cyc["evidence_weighted_totals"],
    )
    if ind["condorcet_winner"] is not None:
        return fail("recompute elected a Condorcet winner on the cycle")
    if not ind["cycles"]:
        return fail("recompute dropped the cycle")
    if set(ind["cycles"][0]) != wanted:
        return fail(f"recompute cycle {ind['cycles']}")

    # Both-states: a transitive profile must NOT report a cycle and MUST
    # name a unique Condorcet winner.
    trans = A.aggregate(F.transitive_scorecards(), rubric, REPO)
    print(
        json.dumps(
            {
                "transitive_condorcet_winner": trans["condorcet_winner"],
                "transitive_cycle_count": len(trans["cycles"]),
                "transitive_ranking": [r["entry_id"] for r in trans["ranking"]],
            },
            sort_keys=True,
        )
    )
    if trans["cycles"]:
        return fail(f"transitive control reported cycles {trans['cycles']}")
    if trans["condorcet_winner"] != "TX":
        return fail(f"transitive winner {trans['condorcet_winner']} want TX")
    if trans["tie_break_applied"]:
        return fail("tie-break must not be required on a unique Condorcet winner")

    # Negative control: stripping cycles from the result is the silent-break
    # failure the test exists to catch. The checker fires on the mutant and
    # stays quiet on the honest result.
    mutant = dict(cyc)
    mutant["cycles"] = []
    mutant_silent = not mutant["cycles"]
    honest_reported = bool(cyc["cycles"])
    if not mutant_silent or not honest_reported:
        return fail("silent-break checker inverted")
    print("silent_break_mutant_detected=True honest_cycles_kept=True")
    print("SUCCESS:ARC-0070-probe1 condorcet-cycle detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
