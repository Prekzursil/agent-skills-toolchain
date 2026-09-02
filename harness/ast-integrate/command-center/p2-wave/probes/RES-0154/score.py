#!/usr/bin/env python3
"""Incentive design: silence on sound work is PASS; volume is not a score input."""
from __future__ import annotations


def score_honest(
    *,
    emitted: int,
    survivors: int,
    surviving_on_known_correct: int,
    billed_hours: float,
) -> dict:
    tn_pass = surviving_on_known_correct == 0
    precision = (survivors / emitted) if emitted else 1.0
    yield_per_hour = (survivors / billed_hours) if billed_hours else 0.0
    # Volume is reported, never multiplied into the score.
    rank_key = (1 if tn_pass else 0, precision, yield_per_hour)
    return {
        "true_negative_pass": tn_pass,
        "precision": round(precision, 6),
        "yield_per_hour": round(yield_per_hour, 6),
        "emitted": emitted,
        "survivors": survivors,
        "surviving_on_known_correct": surviving_on_known_correct,
        "volume_is_score_input": False,
        "rank_key": list(rank_key),
        "rule": (
            "PASS on known-correct iff surviving refutations == 0; "
            "then rank by precision then surviving yield. Emitted count "
            "is not a score input (fan-out B7: never score agents on "
            "output volume)."
        ),
    }


def score_volume(*, emitted: int, billed_hours: float) -> dict:
    yield_per_hour = (emitted / billed_hours) if billed_hours else 0.0
    return {
        "metric": "emitted_per_hour",
        "emitted": emitted,
        "yield_per_hour": round(yield_per_hour, 6),
        "volume_is_score_input": True,
        "rejected_as_success_metric": True,
        "reason": (
            "A volume score rewards a nonzero floor on sound work and "
            "ranks a noisy refuter above an honest one."
        ),
    }
