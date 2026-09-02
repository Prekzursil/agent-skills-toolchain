"""Round-robin Copeland tournament with order-independent ranking (IMP-0287)."""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from typing import Any

METHOD_ROUND_ROBIN = "METHOD_ROUND_ROBIN"
METHOD_SWISS = "METHOD_SWISS"


def transitive_judgements(contestants: list[str]) -> dict[tuple[str, str], str]:
    rank = {c: i for i, c in enumerate(contestants)}
    out: dict[tuple[str, str], str] = {}
    for a, b in itertools.permutations(contestants, 2):
        out[(a, b)] = a if rank[a] < rank[b] else b
    return out


@dataclass
class TournamentResult:
    winner: str | None
    condorcet_winner: str | None
    ranking: list[str]
    scores: dict[str, int]
    matches: list[dict[str, str]]
    method: str
    cycle_reported: bool = False
    stable_winner: bool = False
    cycles: list[list[str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _pairs(contestants: list[str], seed: int) -> list[tuple[str, str]]:
    pairs = list(itertools.combinations(contestants, 2))
    rng = random.Random(seed)
    rng.shuffle(pairs)
    return pairs


def _beats(matches: list[dict[str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for m in matches:
        out.setdefault(m["winner"], set()).add(m["loser"])
        out.setdefault(m["loser"], set())
    return out


def condorcet_winner_of(contestants: list[str], matches: list[dict[str, str]]) -> str | None:
    """The contestant that beat every other one head-to-head, if any."""
    beats = _beats(matches)
    for c in contestants:
        if beats.get(c, set()) >= {o for o in contestants if o != c}:
            return c
    return None


def smith_set(contestants: list[str], scores: dict[str, int], matches: list[dict[str, str]]) -> list[str]:
    """Smallest non-empty set whose members each beat every non-member.

    Size 1 means a Condorcet winner; size > 1 is a top cycle (no head-to-head
    ordering exists among its members) and is reported, never broken.
    """
    beats = _beats(matches)
    ordered = sorted(contestants, key=lambda c: (-scores[c], c))
    for k in range(1, len(ordered) + 1):
        top, rest = ordered[:k], ordered[k:]
        if all(beats.get(t, set()) >= set(rest) for t in top):
            return sorted(top)
    return sorted(ordered)


def run_tournament(
    contestants: list[str],
    judgements: dict[tuple[str, str], str],
    method: str = METHOD_ROUND_ROBIN,
    seed: int = 0,
    swiss_rounds: int = 0,
) -> TournamentResult:
    if method == METHOD_SWISS:
        return _swiss(contestants, judgements, seed, swiss_rounds or 2)
    matches: list[dict[str, str]] = []
    scores = {c: 0 for c in contestants}
    for a, b in _pairs(contestants, seed):
        w = judgements.get((a, b)) or judgements.get((b, a))
        if w is None:
            w = a
        loser = b if w == a else a
        matches.append({"winner": w, "loser": loser, "a": a, "b": b})
        scores[w] += 1
    ranking = sorted(contestants, key=lambda c: (-scores[c], c))
    condorcet = condorcet_winner_of(contestants, matches)
    top = smith_set(contestants, scores, matches)
    cycle = condorcet is None and len(top) > 1
    notes: list[str] = []
    if cycle:
        # A top cycle has no winner: report it, never break it by Copeland/lex.
        notes.append("condorcet-cycle-reported")
        notes.append("winner-withheld:no-head-to-head-order")
    return TournamentResult(
        winner=condorcet,
        condorcet_winner=condorcet,
        ranking=ranking,
        scores=scores,
        matches=matches,
        method=method,
        cycle_reported=cycle,
        stable_winner=condorcet is not None,
        cycles=[top] if cycle else [],
        notes=notes,
    )


def _swiss(
    contestants: list[str],
    judgements: dict[tuple[str, str], str],
    seed: int,
    rounds: int,
) -> TournamentResult:
    rng = random.Random(seed)
    remaining = list(contestants)
    scores = {c: 0 for c in contestants}
    matches: list[dict[str, str]] = []
    played: set[tuple[str, str]] = set()
    for _ in range(rounds):
        pool = remaining[:]
        rng.shuffle(pool)
        while len(pool) >= 2:
            a = pool.pop()
            b = pool.pop()
            key = tuple(sorted((a, b)))
            if key in played and pool:
                pool.append(b)
                continue
            played.add(key)
            w = judgements.get((a, b)) or judgements.get((b, a)) or a
            loser = b if w == a else a
            matches.append({"winner": w, "loser": loser, "a": a, "b": b})
            scores[w] += 1
    ranking = sorted(contestants, key=lambda c: (-scores[c], c))
    return TournamentResult(
        winner=ranking[0],
        condorcet_winner=ranking[0],
        ranking=ranking,
        scores=scores,
        matches=matches,
        method=METHOD_SWISS,
        cycle_reported=False,
        stable_winner=False,
        notes=["swiss:incomplete-pairings;ranking-is-schedule-dependent"],
    )


def condorcet_cycle_judgements(a: str, b: str, c: str) -> dict[tuple[str, str], str]:
    """Rock-paper-scissors: a beats b, b beats c, c beats a."""
    return {
        (a, b): a,
        (b, a): a,
        (b, c): b,
        (c, b): b,
        (c, a): c,
        (a, c): c,
    }


def shuffle_trial(
    contestants: list[str],
    judgements: dict[tuple[str, str], str],
    n: int,
    method: str,
    base_seed: int = 0,
    swiss_rounds: int = 0,
) -> dict[str, Any]:
    winners: list[str] = []
    rankings: list[tuple[str, ...]] = []
    cycle_flags: list[bool] = []
    stable_flags: list[bool] = []
    for i in range(n):
        out = run_tournament(
            contestants,
            judgements,
            method=method,
            seed=base_seed + i,
            swiss_rounds=swiss_rounds,
        )
        winners.append("NONE" if out.winner is None else out.winner)
        rankings.append(tuple(out.ranking))
        cycle_flags.append(out.cycle_reported)
        stable_flags.append(out.stable_winner)
    unique_w = sorted(set(winners))
    unique_r = len(set(rankings))
    order_ind = unique_r == 1 and len(unique_w) == 1
    if method == METHOD_SWISS:
        order_ind = False
    return {
        "n": n,
        "winners": winners,
        "unique_winners": unique_w,
        "unique_ranking_count": unique_r,
        "order_independent": order_ind,
        "order_independent_ranking": unique_r == 1 and method == METHOD_ROUND_ROBIN,
        "cycle_reported_any": any(cycle_flags),
        "cycle_reported_all": bool(cycle_flags) and all(cycle_flags),
        "stable_winner_any": any(stable_flags),
        "method": method,
    }
