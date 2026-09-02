#!/usr/bin/env python3
"""Instant-runoff (IRV) tabulation with an a-priori elimination tie-break.

Procedure (declared before ballots are seen; CNL-0061 local stand-in):
  1. While more than one candidate remains:
  2. Each ballot contributes one first preference among remaining candidates.
     Exhausted ballots (no remaining candidate ranked) are ignored.
  3. If any candidate has a strict majority of non-exhausted ballots, that
     candidate wins.
  4. Otherwise eliminate the candidate with the fewest first preferences.
     Ties: eliminate the lexicographically last candidate id among those tied
     for fewest. This rule is fixed before looking at ballots.
  5. If one candidate remains, that candidate wins.
"""
from __future__ import annotations

from typing import Iterable, Sequence


def irv_winner(
    ballots: Sequence[Sequence[str]],
    candidates: Sequence[str],
) -> str | None:
    remaining = list(candidates)
    if not remaining:
        return None
    while remaining:
        scores = {c: 0 for c in remaining}
        for ballot in ballots:
            for choice in ballot:
                if choice in scores:
                    scores[choice] += 1
                    break
        total = sum(scores.values())
        if total == 0:
            return sorted(remaining)[0]
        majority = [c for c, n in scores.items() if n * 2 > total]
        if majority:
            if len(majority) == 1:
                return majority[0]
            return sorted(majority)[0]
        if len(remaining) == 1:
            return remaining[0]
        fewest = min(scores.values())
        tied = [c for c in remaining if scores[c] == fewest]
        drop = sorted(tied)[-1]
        remaining = [c for c in remaining if c != drop]
    return None


def prefers(ranking: Sequence[str], left: str, right: str) -> bool:
    """True iff `left` is ranked strictly above `right` on `ranking`."""
    if left == right:
        return False
    pos = {c: i for i, c in enumerate(ranking)}
    if left not in pos or right not in pos:
        return False
    return pos[left] < pos[right]


def rankings_equal(a: Iterable[str], b: Iterable[str]) -> bool:
    return list(a) == list(b)
