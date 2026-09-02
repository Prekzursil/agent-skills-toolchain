#!/usr/bin/env python3
"""Author IRV tabulator for CNL-0061.

PROCEDURE IRV-COUNCIL-v1 (LOOKBACK-THEN-LEX-MIN-ELIM):
  1. standing := the option set. Each ballot is a (possibly truncated) ranking
     plus a positive weight (default 1.0). Provenance of weight != 1.0 is
     CNL-0023; this tabulator multiplies the given weight and does not audit it.
  2. Each round, the first remaining preference of every ballot still naming a
     standing option is tallied by weight. Ballots with no remaining standing
     preference are exhausted and drop out of the denominator.
  3. quota := continuing_weight / 2. A unique option with tally > quota
     (strict majority of continuing weight) is elected. 50 percent is not a win.
  4. If one option remains, it is elected. If continuing_weight == 0 while
     options remain, elect lex-min(standing) and flag exhausted_residual.
  5. Otherwise eliminate exactly one last-place option:
       last_place := argmin tally (zeros included).
       If last_place == standing, elect lex-min(standing) (total tie).
       If |last_place| == 1, eliminate that option.
       If |last_place| > 1, apply lookback then lex-min:
         walk previous-round tallies from earliest; among the still-tied set,
         drop anyone who did not have the unique-lowest tally in the first
         round where those tallies differed; if still tied, eliminate
         min(option_id). Never RNG. Never batch-eliminate the whole last-place
         set in one step.
  6. Repeat until a winner is returned. Deterministic given (options, ballots,
     this policy). Replay-safe.

Rejected alternatives recorded in the design note: simultaneous last-place
batch elimination; coin-flip; majority-of-original-n (exhausted ballots
inflating quota).
"""
from __future__ import annotations

from typing import Any

TIE_POLICY = "lookback-then-lex-min-elim"
PROCEDURE_ID = "IRV-COUNCIL-v1"
MAJORITY_RULE = "strict-majority-of-continuing-weight"


def _first_standing(ranks: list[str], standing: set[str]) -> str | None:
    for option in ranks:
        if option in standing:
            return option
    return None


def _tally(
    standing: set[str], ballots: list[tuple[list[str], float]]
) -> tuple[dict[str, float], float, float]:
    tally = {c: 0.0 for c in standing}
    continuing = 0.0
    exhausted = 0.0
    for ranks, weight in ballots:
        top = _first_standing(ranks, standing)
        if top is None:
            exhausted += weight
        else:
            tally[top] += weight
            continuing += weight
    return tally, continuing, exhausted


def _lookback_then_lex_min(
    last_place: list[str], history: list[dict[str, float]]
) -> tuple[str, str]:
    """Return (eliminated_id, rule_used)."""
    tied = set(last_place)
    if len(tied) == 1:
        return next(iter(tied)), "unique-last"
    for prev in history:
        vals = {c: prev[c] for c in tied if c in prev}
        if len(vals) < 2:
            continue
        lowest = min(vals.values())
        weaker = {c for c, v in vals.items() if v == lowest}
        if len(weaker) < len(vals):
            tied = weaker
            if len(tied) == 1:
                return next(iter(tied)), "lookback"
    return min(tied), "lex-min"


def tabulate(options: list[str], ballots: list[tuple[list[str], float]]) -> dict[str, Any]:
    """Run IRV-COUNCIL-v1. ballots are (ranks, weight) with weight > 0."""
    if not options:
        raise ValueError("options must be non-empty")
    option_set = list(dict.fromkeys(options))
    standing = set(option_set)
    history: list[dict[str, float]] = []
    rounds: list[dict[str, Any]] = []
    while standing:
        tally, continuing, exhausted = _tally(standing, ballots)
        rec: dict[str, Any] = {
            "standing": sorted(standing),
            "tally": {k: tally[k] for k in sorted(tally)},
            "continuing_weight": continuing,
            "exhausted_weight": exhausted,
        }
        if continuing <= 0.0:
            winner = min(standing)
            rec["winner"] = winner
            rec["exhausted_residual"] = True
            rec["tie_policy"] = TIE_POLICY
            rounds.append(rec)
            return _finish(winner, rounds, "exhausted-residual")
        quota = continuing / 2.0
        rec["quota"] = quota
        over = sorted(c for c, v in tally.items() if v > quota)
        if len(over) == 1:
            rec["winner"] = over[0]
            rec["majority"] = True
            rounds.append(rec)
            return _finish(over[0], rounds, "strict-majority-continuing")
        if len(standing) == 1:
            winner = next(iter(standing))
            rec["winner"] = winner
            rounds.append(rec)
            return _finish(winner, rounds, "last-remaining")
        min_tally = min(tally.values())
        last_place = sorted(c for c, v in tally.items() if v == min_tally)
        rec["last_place"] = last_place
        rec["min_tally"] = min_tally
        if set(last_place) == standing:
            winner = min(standing)
            rec["winner"] = winner
            rec["total_tie"] = True
            rec["tie_policy"] = TIE_POLICY
            rounds.append(rec)
            return _finish(winner, rounds, "total-tie-lex-min")
        elim, rule = _lookback_then_lex_min(last_place, history)
        rec["eliminated"] = elim
        rec["tie_break_used"] = len(last_place) > 1
        rec["elim_rule"] = rule
        rec["tie_policy"] = TIE_POLICY
        rounds.append(rec)
        history.append(tally)
        standing.remove(elim)
    raise RuntimeError("IRV-COUNCIL-v1 emptied standing without a winner")


def _finish(winner: str, rounds: list[dict[str, Any]], how: str) -> dict[str, Any]:
    return {
        "procedure": PROCEDURE_ID,
        "tie_policy": TIE_POLICY,
        "majority_rule": MAJORITY_RULE,
        "winner": winner,
        "how": how,
        "rounds": rounds,
        "round_count": len(rounds),
    }


def winner(options: list[str], ballots: list[tuple[list[str], float]]) -> str:
    return str(tabulate(options, ballots)["winner"])
