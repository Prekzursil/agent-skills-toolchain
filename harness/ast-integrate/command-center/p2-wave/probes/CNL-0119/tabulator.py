"""Primary voting-method tabulator for CNL-0119.

Dict / first-match scan implementations. recount.py must not import this
module: it re-tabulates with matrix/pointer algorithms instead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
RULES = json.loads((HERE / "fixtures" / "rules.json").read_text(encoding="utf-8"))
METHODS: list[str] = list(RULES["methods"])
APPROVAL_K = int(RULES["approval_k"])
SCORE_VECTOR: tuple[int, ...] = tuple(int(x) for x in RULES["score_vector"])


def _rankings(profile: dict) -> list[list[str]]:
    return [list(b["ranking"]) for b in profile["ballots"]]


def _cands(profile: dict) -> list[str]:
    return list(profile["candidates"])


def _first_continuing(ranking: Iterable[str], remaining: set[str]) -> str | None:
    for c in ranking:
        if c in remaining:
            return c
    return None


def plurality(profile: dict) -> str:
    remaining = set(_cands(profile))
    counts: dict[str, int] = {c: 0 for c in remaining}
    for r in _rankings(profile):
        top = _first_continuing(r, remaining)
        if top is not None:
            counts[top] += 1
    best = max(counts.values())
    tied = [c for c, v in counts.items() if v == best]
    return min(tied)


def irv(profile: dict) -> str:
    remaining = set(_cands(profile))
    rankings = _rankings(profile)
    while remaining:
        counts: dict[str, int] = {c: 0 for c in remaining}
        for r in rankings:
            top = _first_continuing(r, remaining)
            if top is not None:
                counts[top] += 1
        total = sum(counts.values())
        majority = [c for c, v in counts.items() if total and v * 2 > total]
        if len(majority) == 1:
            return majority[0]
        if len(remaining) == 1:
            return next(iter(remaining))
        min_v = min(counts[c] for c in remaining)
        losers = [c for c in remaining if counts[c] == min_v]
        remaining.remove(max(losers))
    raise RuntimeError("IRV eliminated every candidate")


def borda(profile: dict) -> str:
    cands = _cands(profile)
    m = len(cands)
    scores = {c: 0 for c in cands}
    for r in _rankings(profile):
        for i, c in enumerate(r):
            scores[c] += m - 1 - i
    best = max(scores.values())
    return min(c for c, v in scores.items() if v == best)


def approval_top2(profile: dict) -> str:
    cands = _cands(profile)
    scores = {c: 0 for c in cands}
    k = APPROVAL_K
    for r in _rankings(profile):
        for c in r[:k]:
            scores[c] += 1
    best = max(scores.values())
    return min(c for c, v in scores.items() if v == best)


def score_5310(profile: dict) -> str:
    cands = _cands(profile)
    scores = {c: 0 for c in cands}
    for r in _rankings(profile):
        for i, c in enumerate(r):
            if i < len(SCORE_VECTOR):
                scores[c] += SCORE_VECTOR[i]
    best = max(scores.values())
    return min(c for c, v in scores.items() if v == best)


def copeland_minimax(profile: dict) -> str:
    cands = _cands(profile)
    pw = {a: {b: 0 for b in cands if b != a} for a in cands}
    for r in _rankings(profile):
        for i, a in enumerate(r):
            for b in r[i + 1 :]:
                pw[a][b] += 1
    copeland = {}
    for a in cands:
        wins = losses = 0
        for b in cands:
            if a == b:
                continue
            if pw[a][b] > pw[b][a]:
                wins += 1
            elif pw[a][b] < pw[b][a]:
                losses += 1
        copeland[a] = wins - losses
    best_c = max(copeland.values())
    tied = [c for c in cands if copeland[c] == best_c]
    if len(tied) == 1:
        return tied[0]
    max_against = {}
    for a in tied:
        max_against[a] = max(pw[b][a] for b in cands if b != a)
    best_m = min(max_against.values())
    mm = [c for c in tied if max_against[c] == best_m]
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


def winner_set(profile: dict) -> set[str]:
    return set(winners(profile).values())


def methods_disagree(profile: dict) -> bool:
    return len(winner_set(profile)) > 1
