"""Named-pair if-ladder: the mechanism the unit exists to refuse.

Only the two catalog examples are hard-coded. Any other predicate-identical
pair is silently accepted. Used as the losing option that the solver is
measured against, not as the checker.
"""
from __future__ import annotations

NAMED_UNORDERED = frozenset(
    {
        frozenset({"proposer", "judge"}),
        frozenset({"critic", "juror"}),
    }
)


def ladder_incompatible(a: str, b: str) -> bool:
    if a == b:
        return False
    return frozenset({a, b}) in NAMED_UNORDERED


def ladder_scan(names: list[str]) -> dict:
    misses = []
    hits = []
    for a in names:
        for b in names:
            if a > b:
                continue
            if a == b:
                continue
            if ladder_incompatible(a, b):
                hits.append(f"{a}+{b}")
    return {
        "named_pairs": sorted("+".join(sorted(p)) for p in NAMED_UNORDERED),
        "ladder_hits": hits,
    }


def missed_by_ladder(solver_unordered: list[str], names: list[str]) -> list[str]:
    named = {frozenset(p.split("+")) for p in solver_unordered}
    ladder = set(NAMED_UNORDERED)
    misses = []
    for pair in named:
        if pair not in ladder:
            misses.append("+".join(sorted(pair)))
    return sorted(misses)
