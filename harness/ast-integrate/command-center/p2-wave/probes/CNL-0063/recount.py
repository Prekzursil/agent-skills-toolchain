"""Independent recount: different walk and different Schulze algorithm.

Signal 2 is not a second call to tabulate.pairwise_matrix / schulze_paths.
Pairwise cells are accumulated by walking each ballot's adjacent rank pairs
(every earlier-ranked candidate vs every later-ranked one). Schulze strongest
paths are widest-path Dijkstra from each source, not Floyd-Warshall.
"""
from __future__ import annotations

from typing import Any

INF = 10**12


def pairwise_by_rank_pairs(
    candidates: list[str], ballots: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    matrix = {a: {b: 0 for b in candidates} for a in candidates}
    allowed = set(candidates)
    for ball in ballots:
        ranking = ball["ranking"]
        w = int(ball["weight"])
        if set(ranking) != allowed:
            raise ValueError("ballot ranking does not match candidate set")
        for i, higher in enumerate(ranking):
            for lower in ranking[i + 1 :]:
                matrix[higher][lower] += w
    return matrix


def widest_paths_from(
    matrix: dict[str, dict[str, int]], src: str, candidates: list[str]
) -> dict[str, int]:
    strength = {c: 0 for c in candidates}
    strength[src] = INF
    remaining = set(candidates)
    while remaining:
        u = max(remaining, key=lambda c: strength[c])
        remaining.remove(u)
        if strength[u] == 0 and u != src:
            continue
        for v in remaining:
            if matrix[u][v] <= matrix[v][u]:
                continue
            edge = matrix[u][v]
            via = edge if strength[u] == INF else min(strength[u], edge)
            if via > strength[v]:
                strength[v] = via
    strength[src] = 0
    return strength


def schulze_via_dijkstra(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> dict[str, Any]:
    paths = {a: widest_paths_from(matrix, a, candidates) for a in candidates}
    scores = {a: 0 for a in candidates}
    for a in candidates:
        for b in candidates:
            if a != b and paths[a][b] > paths[b][a]:
                scores[a] += 1
    best = max(scores.values())
    tied = [c for c in candidates if scores[c] == best]
    return {"paths": paths, "scores": scores, "winner": tied[0]}


def condorcet_from_cells(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> str | None:
    for a in candidates:
        if all(matrix[a][b] > matrix[b][a] for b in candidates if b != a):
            return a
    return None


def recount(
    candidates: list[str], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    ballots: list[dict[str, Any]] = []
    for row in rows:
        ranking = list(row["ranking"])
        weight = int(row.get("weight", 1))
        count = int(row.get("count", 1))
        for _ in range(count):
            ballots.append({"ranking": ranking, "weight": weight})
    matrix = pairwise_by_rank_pairs(candidates, ballots)
    schulze = schulze_via_dijkstra(matrix, candidates)
    cw = condorcet_from_cells(matrix, candidates)
    return {
        "condorcet_winner": cw,
        "cycle_detected": cw is None,
        "pairwise": matrix,
        "schulze_scores": schulze["scores"],
        "winner": cw if cw is not None else schulze["winner"],
    }
