"""Independent recount tabulator for CNL-0119.

Does not import tabulator.py. IRV uses continuing-ballot pointers.
Pairwise uses an n-by-n integer matrix over sorted candidate ids.
Plurality / Borda / approval / score walk candidates rather than ballots-first
aggregation dicts used by the primary tabulator.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = json.loads((HERE / "fixtures" / "rules.json").read_text(encoding="utf-8"))
METHODS: list[str] = list(RULES["methods"])
APPROVAL_K = int(RULES["approval_k"])
SCORE_VECTOR: tuple[int, ...] = tuple(int(x) for x in RULES["score_vector"])


def _rankings(profile: dict) -> list[list[str]]:
    return [list(b["ranking"]) for b in profile["ballots"]]


def _order(profile: dict) -> list[str]:
    return sorted(profile["candidates"])


def plurality(profile: dict) -> str:
    order = _order(profile)
    rankings = _rankings(profile)
    counts = []
    for c in order:
        n = 0
        for r in rankings:
            if r and r[0] == c:
                n += 1
        counts.append(n)
    best = max(counts)
    tied = [order[i] for i, v in enumerate(counts) if v == best]
    return min(tied)


def irv(profile: dict) -> str:
    """Continuing-pointer IRV (not first-match rescans of each ranking)."""
    order = _order(profile)
    rankings = _rankings(profile)
    remaining = set(order)
    ptr = [0] * len(rankings)
    while remaining:
        counts = {c: 0 for c in remaining}
        for i, r in enumerate(rankings):
            while ptr[i] < len(r) and r[ptr[i]] not in remaining:
                ptr[i] += 1
            if ptr[i] < len(r):
                counts[r[ptr[i]]] += 1
        total = sum(counts.values())
        lead = None
        lead_v = -1
        for c in sorted(remaining):
            v = counts[c]
            if v > lead_v:
                lead, lead_v = c, v
        if total and lead_v * 2 > total:
            return lead  # type: ignore[return-value]
        if len(remaining) == 1:
            return next(iter(remaining))
        min_v = min(counts[c] for c in remaining)
        drop = max(c for c in remaining if counts[c] == min_v)
        remaining.remove(drop)
    raise RuntimeError("IRV recount emptied remaining")


def borda(profile: dict) -> str:
    order = _order(profile)
    m = len(order)
    rankings = _rankings(profile)
    scores = []
    for c in order:
        s = 0
        for r in rankings:
            s += m - 1 - r.index(c)
        scores.append(s)
    best = max(scores)
    tied = [order[i] for i, v in enumerate(scores) if v == best]
    return min(tied)


def approval_top2(profile: dict) -> str:
    order = _order(profile)
    rankings = _rankings(profile)
    k = APPROVAL_K
    scores = []
    for c in order:
        n = sum(1 for r in rankings if c in r[:k])
        scores.append(n)
    best = max(scores)
    tied = [order[i] for i, v in enumerate(scores) if v == best]
    return min(tied)


def score_5310(profile: dict) -> str:
    order = _order(profile)
    rankings = _rankings(profile)
    scores = []
    for c in order:
        s = 0
        for r in rankings:
            i = r.index(c)
            if i < len(SCORE_VECTOR):
                s += SCORE_VECTOR[i]
        scores.append(s)
    best = max(scores)
    tied = [order[i] for i, v in enumerate(scores) if v == best]
    return min(tied)


def copeland_minimax(profile: dict) -> str:
    order = _order(profile)
    n = len(order)
    idx = {c: i for i, c in enumerate(order)}
    matrix = [[0] * n for _ in range(n)]
    for r in _rankings(profile):
        pos = {c: k for k, c in enumerate(r)}
        for i, a in enumerate(order):
            for j, b in enumerate(order):
                if i == j:
                    continue
                if pos[a] < pos[b]:
                    matrix[i][j] += 1
    copeland = []
    for i in range(n):
        wins = losses = 0
        for j in range(n):
            if i == j:
                continue
            if matrix[i][j] > matrix[j][i]:
                wins += 1
            elif matrix[i][j] < matrix[j][i]:
                losses += 1
        copeland.append(wins - losses)
    best_c = max(copeland)
    tied_idx = [i for i in range(n) if copeland[i] == best_c]
    if len(tied_idx) == 1:
        return order[tied_idx[0]]
    max_against = []
    for i in tied_idx:
        against = max(matrix[j][i] for j in range(n) if j != i)
        max_against.append(against)
    best_m = min(max_against)
    mm = [order[tied_idx[k]] for k, v in enumerate(max_against) if v == best_m]
    return min(mm)


TABULATORS = {
    "plurality": plurality,
    "irv": irv,
    "borda": borda,
    "approval_top2": approval_top2,
    "score_5310": score_5310,
    "copeland_minimax": copeland_minimax,
}


def winners(profile: dict) -> dict[str, str]:
    return {name: fn(profile) for name, fn in TABULATORS.items()}
