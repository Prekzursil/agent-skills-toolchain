#!/usr/bin/env python3
"""IMP-0296 probe 2: mediator neutrality vs biased negative control.

Starts from the public simulate/experiment API (not an author summary):
recomputes midpoint independently and measures shift toward the declared prior
over 10 matched runs. A biased mediator must move the settlement; a neutral
one must not mix the prior into suggestions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.negotiate import (  # noqa: E402
    MediatorHasNoVote,
    NegotiationSession,
    Participant,
    Role,
    run_matched_pair_experiment,
    shift_toward_prior,
)

NEUTRAL_MAX_ABS_SHIFT = 1e-9
BIASED_MIN_SHIFT = 0.08
N_RUNS = 10
PRIOR = 0.95
BIAS = 0.55


def _recompute_midpoint_independent() -> dict:
    a = Participant(id="alice", preferred=0.8)
    b = Participant(id="bob", preferred=0.2)
    med = Participant(id="med", role=Role.MEDIATOR, prior=PRIOR, bias=0.0)
    s = NegotiationSession((a, b), mediator=med)
    s.propose("alice", 0.80)
    s.counter("bob", 0.20)
    sug = s.suggest()
    independent_mid = (0.80 + 0.20) / 2.0
    if abs(sug.value - independent_mid) > 1e-12:
        raise AssertionError(
            f"neutral suggestion {sug.value} != independent midpoint {independent_mid}"
        )
    if sug.uses_prior or sug.prior is None:
        # prior may be declared; it must not enter the value
        pass
    if sug.uses_prior:
        raise AssertionError("neutral suggestion flagged uses_prior")
    if abs(sug.value - PRIOR) < 0.2:
        raise AssertionError("neutral suggestion collapsed onto the prior")
    try:
        s.vote("med", PRIOR)
        raise AssertionError("mediator vote must raise")
    except MediatorHasNoVote:
        pass
    biased = Participant(id="med", role=Role.MEDIATOR, prior=PRIOR, bias=BIAS)
    s2 = NegotiationSession((a, b), mediator=biased)
    s2.propose("alice", 0.80)
    s2.counter("bob", 0.20)
    sug_b = s2.suggest()
    expected = (1.0 - BIAS) * independent_mid + BIAS * PRIOR
    if abs(sug_b.value - expected) > 1e-12:
        raise AssertionError(f"biased suggestion {sug_b.value} != {expected}")
    if not sug_b.uses_prior:
        raise AssertionError("biased suggestion must use the prior")
    return {
        "neutral_suggestion": sug.value,
        "independent_midpoint": independent_mid,
        "biased_suggestion": sug_b.value,
        "biased_expected": expected,
        "mediator_vote_refused": True,
    }


def main() -> int:
    indep = _recompute_midpoint_independent()
    exp = run_matched_pair_experiment(N_RUNS, prior=PRIOR, bias=BIAS)
    if exp["n"] != N_RUNS:
        raise AssertionError(exp["n"])
    if set(exp["ledger_parties"]) != {"alice", "bob"}:
        raise AssertionError(f"ledger parties {exp['ledger_parties']}")
    nshift = float(exp["mean_neutral_shift_toward_prior"])
    bshift = float(exp["mean_biased_shift_toward_prior"])
    if abs(nshift) > NEUTRAL_MAX_ABS_SHIFT:
        raise AssertionError(
            f"neutral mediator shifted outcomes toward prior: mean_shift={nshift}"
        )
    if exp["any_neutral_used_prior"]:
        raise AssertionError("neutral run mixed the declared prior into a suggestion")
    if bshift <= BIASED_MIN_SHIFT:
        raise AssertionError(
            f"biased mediator negative control did not shift enough: {bshift}"
        )
    if not exp["all_biased_used_prior"]:
        raise AssertionError("biased mediator must use prior on every run")
    # Detector discrimination: the same shift function applied to identical
    # settlements would be ~0; the biased arm is the only arm that moves.
    if bshift <= abs(nshift) + BIASED_MIN_SHIFT:
        raise AssertionError("biased vs neutral shifts do not discriminate")
    # Hand-check first pair with the exported metric (reviewer starts from tests).
    p0 = exp["pairs"][0]
    rec = shift_toward_prior(PRIOR, p0["without"], p0["neutral"])
    if abs(rec - p0["neutral_shift_toward_prior"]) > 1e-12:
        raise AssertionError("shift metric disagrees with recorded pair")
    payload = {
        "probe": "probe2-mediator-neutrality",
        "unit_id": "IMP-0296",
        "pass": True,
        "n": exp["n"],
        "prior": PRIOR,
        "mean_without": exp["mean_without"],
        "mean_neutral": exp["mean_neutral"],
        "mean_biased": exp["mean_biased"],
        "mean_neutral_shift_toward_prior": nshift,
        "mean_biased_shift_toward_prior": bshift,
        "any_neutral_used_prior": exp["any_neutral_used_prior"],
        "all_biased_used_prior": exp["all_biased_used_prior"],
        "ledger_parties": exp["ledger_parties"],
        "independent": indep,
        "negative_control": "biased_mediator_shift",
        "negative_control_fired": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:IMP-0296-probe2 "
        f"neutral_shift={nshift} biased_shift={bshift} n={N_RUNS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
