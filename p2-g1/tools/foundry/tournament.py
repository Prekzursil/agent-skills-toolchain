"""Tournament ranking (IMP-0254)."""
from __future__ import annotations

from typing import Any

from tools.foundry import counters


def ranking_from_matrix(matrix: list[list[int]], candidate_ids: list[str]) -> list[dict[str, Any]]:
    scores = []
    for i, cid in enumerate(candidate_ids):
        scores.append((sum(matrix[i]), cid, i))
    scores.sort(key=lambda t: (-t[0], t[1]))
    # ties share rank
    ranking = []
    last_score = None
    rank = 0
    for n, (score, cid, _) in enumerate(scores, 1):
        if score != last_score:
            rank = n
            last_score = score
        ranking.append({"id": cid, "rank": rank, "score": score})
    return ranking


def run_tournament(payload: dict[str, Any]) -> dict[str, Any]:
    counters.inc("tournament.run")
    cands = list(payload.get("candidates") or [])
    ids = [str(c["id"]) for c in cands]
    metrics = {str(c["id"]): float(c.get("metric") or 0) for c in cands}
    n = len(ids)
    matrix = [[0 for _ in range(n)] for _ in range(n)]
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i == j:
                continue
            if metrics[a] > metrics[b]:
                matrix[i][j] = 1
            elif metrics[a] == metrics[b]:
                matrix[i][j] = 0
            else:
                matrix[i][j] = 0
    ranking = ranking_from_matrix(matrix, ids)
    has_tie = len({r["rank"] for r in ranking}) < len(ranking)
    return {
        "has_tie": has_tie,
        "pairwise_matrix": matrix,
        "candidate_ids": ids,
        "ranking": ranking,
    }
