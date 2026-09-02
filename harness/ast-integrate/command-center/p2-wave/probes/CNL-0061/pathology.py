#!/usr/bin/env python3
"""Pathology detectors for CNL-0061: non-monotonicity and later-no-harm."""
from __future__ import annotations

from itertools import permutations
from typing import Any, Callable

IrvFn = Callable[[list[str], list[tuple[list[str], float]]], dict[str, Any]]


def pair_winners(
    irv_fn: IrvFn,
    options: list[str],
    before: list[tuple[list[str], float]],
    after: list[tuple[list[str], float]],
) -> dict[str, Any]:
    b = irv_fn(options, before)
    a = irv_fn(options, after)
    return {
        "before_winner": b["winner"],
        "after_winner": a["winner"],
        "before_how": b.get("how"),
        "after_how": a.get("how"),
        "before_rounds": b.get("rounds"),
        "after_rounds": a.get("rounds"),
        "flipped": b["winner"] != a["winner"],
    }


def nonmonotonicity_check(
    irv_fn: IrvFn,
    options: list[str],
    original: list[tuple[list[str], float]],
    raised: list[tuple[list[str], float]],
    raised_candidate: str,
) -> dict[str, Any]:
    """FIRES when raising the original winner on one ballot unseats them."""
    p = pair_winners(irv_fn, options, original, raised)
    fired = bool(p["before_winner"] == raised_candidate and p["flipped"])
    p.update(
        {
            "raised_candidate": raised_candidate,
            "fired": fired,
            "silent": not fired,
            "pathology": "non-monotonicity",
        }
    )
    return p


def later_no_harm_check(
    method_fn: IrvFn,
    options: list[str],
    truncated: list[tuple[list[str], float]],
    completed: list[tuple[list[str], float]],
    first_choice: str,
) -> dict[str, Any]:
    """FIRES when adding later ranks unseats a first-choice who was winning."""
    p = pair_winners(method_fn, options, truncated, completed)
    fired = bool(p["before_winner"] == first_choice and p["flipped"])
    p.update(
        {
            "first_choice": first_choice,
            "fired": fired,
            "silent": not fired,
            "pathology": "later-no-harm",
        }
    )
    return p


def second_place_plurality(
    options: list[str], ballots: list[tuple[list[str], float]]
) -> dict[str, Any]:
    """Planted non-council method that can violate later-no-harm.

    If any ballot has a second rank, elect the lex-min option among those with
    the most second-place weight. Otherwise fall back to first-place plurality.
    Completing a truncated [A] ballot to [A, B] can therefore unseat A.
    """
    second = {c: 0.0 for c in options}
    first = {c: 0.0 for c in options}
    any_second = False
    for ranks, weight in ballots:
        if ranks:
            if ranks[0] in first:
                first[ranks[0]] += weight
        if len(ranks) >= 2 and ranks[1] in second:
            second[ranks[1]] += weight
            any_second = True
    scores = second if any_second else first
    best = max(scores.values())
    win = min(c for c, v in scores.items() if v == best)
    return {
        "winner": win,
        "how": "second-place-plurality" if any_second else "first-place-fallback",
        "rounds": [],
        "scores": scores,
    }


def raise_to_first(ranks: tuple[str, ...], cand: str) -> tuple[str, ...] | None:
    if cand not in ranks or ranks[0] == cand:
        return None
    rest = [x for x in ranks if x != cand]
    return (cand, *rest)


def census_three_cand_raise_to_first(irv_fn: IrvFn, n: int) -> int:
    """Count (profile, source-type) pairs at roster n where raising the winner
    to first on one ballot of that type flips the winner. 3 complete rankings.
    """
    types = list(permutations(("A", "B", "C")))
    hits = 0

    def rec(pos: int, left: int, acc: tuple[int, ...]):
        if pos == 5:
            yield acc + (left,)
            return
        for k in range(left + 1):
            yield from rec(pos + 1, left - k, acc + (k,))

    options = ["A", "B", "C"]
    for counts in rec(0, n, ()):
        ballots: list[tuple[list[str], float]] = []
        for typ, k in zip(types, counts):
            for _ in range(k):
                ballots.append((list(typ), 1.0))
        w0 = irv_fn(options, ballots)["winner"]
        for i, typ in enumerate(types):
            if counts[i] == 0:
                continue
            lifted = raise_to_first(typ, w0)
            if lifted is None:
                continue
            new_counts = list(counts)
            new_counts[i] -= 1
            new_counts[types.index(lifted)] += 1
            after: list[tuple[list[str], float]] = []
            for typ2, k2 in zip(types, new_counts):
                for _ in range(k2):
                    after.append((list(typ2), 1.0))
            if irv_fn(options, after)["winner"] != w0:
                hits += 1
    return hits
