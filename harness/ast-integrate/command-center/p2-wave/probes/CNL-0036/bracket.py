"""Single-elimination bracket with declared seeding and match tie-break.

Pairwise outcomes are an oracle (who beats whom). This module does not
break Condorcet cycles; a cycle in the oracle typically makes the knockout
winner seeding-dependent, which the invariance gate is required to report
rather than hide. Cycle *completion* is CNL-0063's job.
"""
from __future__ import annotations

from collections import Counter
from itertools import permutations
from typing import Iterable

BYE = "__BYE__"
TIE_LEXICOGRAPHIC_ID = "lexicographic_id"
TIE_LEFT_SLOT = "left_slot"
TIE_REFUSE = "refuse"


class SpecError(ValueError):
    pass


def next_power_of_two(n: int) -> int:
    if n < 1:
        raise SpecError("need at least one option")
    p = 1
    while p < n:
        p *= 2
    return p


def standard_slot_seeds(n_slots: int) -> list[int]:
    """Seed numbers 1..n_slots in visit order (1 plays n, 2 plays n-1, ...)."""
    if n_slots < 1 or n_slots & (n_slots - 1):
        raise SpecError("n_slots must be a power of two")
    if n_slots == 1:
        return [1]
    out: list[int] = []
    for seed in standard_slot_seeds(n_slots // 2):
        out.append(seed)
        out.append(n_slots + 1 - seed)
    return out


def place_options(seed_order: list[str], n_slots: int) -> list[str]:
    """seed_order[0] is seed 1. Unfilled seeds are BYE."""
    if len(seed_order) != len(set(seed_order)):
        raise SpecError("seed_order must be unique")
    slots = [BYE] * n_slots
    for position, seed_num in enumerate(standard_slot_seeds(n_slots)):
        idx = seed_num - 1
        if idx < len(seed_order):
            slots[position] = seed_order[idx]
    return slots


def beats_set(pairs: Iterable[list[str] | tuple[str, str]]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for pair in pairs:
        a, b = pair[0], pair[1]
        if a == b:
            raise SpecError(f"option cannot beat itself: {a}")
        if (b, a) in out:
            raise SpecError(f"contradictory beats for {a},{b}")
        out.add((a, b))
    return out


def tie_set(pairs: Iterable[list[str] | tuple[str, str]]) -> set[frozenset[str]]:
    out: set[frozenset[str]] = set()
    for pair in pairs:
        a, b = pair[0], pair[1]
        if a == b:
            raise SpecError(f"option cannot tie itself: {a}")
        out.add(frozenset((a, b)))
    return out


def assert_complete(
    options: list[str],
    beats: set[tuple[str, str]],
    ties: set[frozenset[str]],
) -> None:
    for i, a in enumerate(options):
        for b in options[i + 1 :]:
            directed = (a, b) in beats or (b, a) in beats
            tied = frozenset((a, b)) in ties
            if directed and tied:
                raise SpecError(f"{a} vs {b} is both a beat and a tie")
            if not directed and not tied:
                raise SpecError(f"incomplete oracle: {a} vs {b}")


def play_match(
    left: str,
    right: str,
    beats: set[tuple[str, str]],
    ties: set[frozenset[str]],
    tie_break: str,
) -> str:
    if left == BYE:
        return right
    if right == BYE:
        return left
    if left == right:
        return left
    if (left, right) in beats:
        return left
    if (right, left) in beats:
        return right
    if frozenset((left, right)) not in ties:
        raise SpecError(f"unresolved match {left} vs {right} (not a declared tie)")
    if tie_break == TIE_LEXICOGRAPHIC_ID:
        return min(left, right)
    if tie_break == TIE_LEFT_SLOT:
        return left
    if tie_break == TIE_REFUSE:
        raise SpecError(f"declared tie refused: {left} vs {right}")
    raise SpecError(f"unknown tie_break={tie_break!r}")


def run_bracket(
    seed_order: list[str],
    beats: set[tuple[str, str]],
    ties: set[frozenset[str]],
    tie_break: str = TIE_LEXICOGRAPHIC_ID,
) -> str:
    n_slots = next_power_of_two(len(seed_order))
    round_slots = place_options(seed_order, n_slots)
    while len(round_slots) > 1:
        nxt: list[str] = []
        for i in range(0, len(round_slots), 2):
            nxt.append(
                play_match(
                    round_slots[i],
                    round_slots[i + 1],
                    beats,
                    ties,
                    tie_break,
                )
            )
        round_slots = nxt
    return round_slots[0]


def sweep(
    options: list[str],
    beats: set[tuple[str, str]],
    ties: set[frozenset[str]],
    tie_break: str = TIE_LEXICOGRAPHIC_ID,
) -> dict:
    assert_complete(options, beats, ties)
    winners: list[str] = []
    for order in permutations(options):
        winners.append(
            run_bracket(list(order), beats, ties, tie_break)
        )
    counts = Counter(winners)
    n_perm = len(winners)
    n_distinct = len(counts)
    modal_n = max(counts.values()) if counts else 0
    invariance_rate = modal_n / float(n_perm) if n_perm else 0.0
    fires = n_distinct > 1
    return {
        "counts": dict(sorted(counts.items())),
        "fires": fires,
        "invariance_rate": invariance_rate,
        "modal_winner": counts.most_common(1)[0][0] if counts else None,
        "n_distinct_winners": n_distinct,
        "n_permutations": n_perm,
        "options": list(options),
        "reason": (
            "seeding-dependent" if fires else "seeding-invariant"
        ),
        "tie_break": tie_break,
        "winners": winners,
    }


def gate_unique_winner(row: dict, threshold_reject_below: float = 1.0) -> dict:
    """Refuse a unique published winner when invariance_rate < threshold."""
    rate = float(row["invariance_rate"])
    refuse = rate < threshold_reject_below
    return {
        "fires": refuse,
        "invariance_rate": rate,
        "n_distinct_winners": row["n_distinct_winners"],
        "publication": (
            "SEEDING-DEPENDENT-REFUSED" if refuse else "INVARIANT-UNIQUE-WINNER"
        ),
        "published_winner": (
            None if refuse else row["modal_winner"]
        ),
        "threshold_reject_below": threshold_reject_below,
    }
