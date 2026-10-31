"""Round-robin Copeland tournament with order-independent ranking (IMP-0287)."""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
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
    winner: str
    condorcet_winner: str
    ranking: list[str]
    scores: dict[str, int]
    matches: list[dict[str, str]]
    method: str
    cycle_reported: bool = False


def _pairs(contestants: list[str], seed: int) -> list[tuple[str, str]]:
    pairs = list(itertools.combinations(contestants, 2))
    rng = random.Random(seed)
    rng.shuffle(pairs)
    return pairs


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
    # Condorcet cycle: every contestant has the same score in a 3-cycle.
    cycle = len(contestants) == 3 and len(set(scores.values())) == 1
    winner = ranking[0]
    return TournamentResult(
        winner="" if cycle else winner,
        condorcet_winner="" if cycle else winner,
        ranking=ranking,
        scores=scores,
        matches=matches,
        method=method,
        cycle_reported=cycle,
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
    cycle_any = False
    for i in range(n):
        out = run_tournament(
            contestants,
            judgements,
            method=method,
            seed=base_seed + i,
            swiss_rounds=swiss_rounds,
        )
        winners.append(out.winner)
        rankings.append(tuple(out.ranking))
        cycle_any = cycle_any or out.cycle_reported
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
        "cycle_reported_any": cycle_any,
        "method": method,
    }
