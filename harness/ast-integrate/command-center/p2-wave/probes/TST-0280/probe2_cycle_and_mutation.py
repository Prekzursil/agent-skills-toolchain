#!/usr/bin/env python3
"""Probe 2: Condorcet cycle recording + majority-threshold mutation control.

Mechanically different from probe 1 (no 10k random monotonicity loop).
Recomputes Wilson intervals from the raw k/n counts as the statistics review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote.axiom_tests import (  # noqa: E402
    cycle_report,
    mutation_control,
    run_monotonicity,
    wilson_interval,
)

UNIT = "TST-0280"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    cycle = cycle_report()
    if not cycle["pass"]:
        return fail(f"cycle fixture failed {cycle}")
    if cycle["crashed"]:
        return fail("pairwise crashed on a cycle")
    if cycle["silent_arbitrary_pick"]:
        return fail("cycle resolved without recording the rule")
    if not cycle["cycle_recorded"]:
        return fail("cycle not recorded")
    if not cycle["resolution_rule"]:
        return fail("no documented resolution rule")
    if cycle["deterministic_winner"] is None:
        return fail("cycle produced no documented winner")

    mut = mutation_control(n=200)
    if not mut["pass"]:
        return fail(f"mutation control failed { {k: mut[k] for k in mut if k != 'mutant_threshold'} }")
    if not mut["threshold_flipped"]:
        return fail("mutant majority threshold did not introduce a violation")
    if not mut["went_red"]:
        return fail("property suite did not go red under the off-by-one mutant")

    # Independent statistics recompute from raw k/n (majority monotonicity sample).
    raw = run_monotonicity("majority", n=2000, mutant=False)
    recomputed = wilson_interval(
        int(raw["n_violations"]),
        int(raw["n_applicable"] or raw["n_profiles"]),
    )
    stored = raw["wilson"]
    if abs(recomputed["rate"] - stored["rate"]) > 1e-12:
        return fail("wilson rate mismatch on recompute")
    if abs(recomputed["low"] - stored["low"]) > 1e-9:
        return fail("wilson low mismatch on recompute")
    if abs(recomputed["high"] - stored["high"]) > 1e-9:
        return fail("wilson high mismatch on recompute")
    if raw["n_violations"] != 0:
        return fail("majority monotonicity sample was not clean")

    payload = {
        "probe": "probe2-cycle-and-mutation",
        "unit_id": UNIT,
        "pass": True,
        "cycle_recorded": cycle["cycle_recorded"],
        "cycle_winner": cycle["deterministic_winner"],
        "resolution_rule": cycle["resolution_rule"],
        "cycle_members": cycle["outcome"]["cycle_members"],
        "mutation": {
            "threshold_flipped": mut["threshold_flipped"],
            "went_red": mut["went_red"],
            "honest_suite_red": mut["honest_suite_red"],
            "mutant_suite_red": mut["mutant_suite_red"],
            "threshold_honest_violations": mut["threshold_honest_violations"],
            "threshold_mutant_violations": mut["threshold_mutant_violations"],
            "mutant_threshold_used": mut["mutant_threshold"].get("threshold_used"),
            "honest_threshold_used": mut["honest_threshold"].get("threshold_used"),
        },
        "reviewer_stats": {
            "method": "majority",
            "n_profiles": raw["n_profiles"],
            "n_applicable": raw["n_applicable"],
            "n_violations": raw["n_violations"],
            "wilson_stored": stored,
            "wilson_recomputed": recomputed,
            "bits_sha256": raw.get("bits_sha256"),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"cycle={cycle['cycle_recorded']} winner={cycle['deterministic_winner']} "
        f"mutant_red={mut['mutant_suite_red']} wilson_rate={recomputed['rate']}"
    )
    print(f"SUCCESS:{UNIT}-probe2 cycle recorded; mutant threshold turns suite red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
