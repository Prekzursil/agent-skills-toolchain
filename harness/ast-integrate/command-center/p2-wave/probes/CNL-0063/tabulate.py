"""Pairwise Condorcet tabulation with a freeze-before-ballots cycle rule.

Declared completion for this unit: Schulze (beatpath / widest path).
A different completion (plurality inside the Smith set) is implemented only so
the load-bearing swap can be shown to change the winner on the same ballots.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

ALLOWED_COMPLETIONS = (
    "schulze",
    "plurality_in_smith",
    "minimax_winning_votes",
)
DECLARED_COMPLETION = "schulze"
SWAP_COMPLETION = "plurality_in_smith"
METHOD = "pairwise_condorcet"


class SpecError(ValueError):
    pass


def freeze_token(cycle_completion: str, candidate_order: list[str]) -> str:
    payload = {
        "candidate_order": list(candidate_order),
        "cycle_completion": cycle_completion,
        "method": METHOD,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def freeze_spec(
    cycle_completion: str, candidate_order: list[str]
) -> dict[str, Any]:
    if cycle_completion not in ALLOWED_COMPLETIONS:
        raise SpecError(f"unknown cycle_completion={cycle_completion!r}")
    if not candidate_order or len(set(candidate_order)) != len(candidate_order):
        raise SpecError("candidate_order must be a unique non-empty list")
    token = freeze_token(cycle_completion, candidate_order)
    return {
        "candidate_order": list(candidate_order),
        "cycle_completion": cycle_completion,
        "freeze_token": token,
        "ingested": False,
        "method": METHOD,
    }


def expand_ballots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        ranking = list(row["ranking"])
        weight = row.get("weight", 1)
        count = int(row.get("count", 1))
        provenance_ref = row.get("provenance_ref")
        if weight != 1 and not provenance_ref:
            raise SpecError(
                f"ballot[{i}] weight={weight} lacks provenance_ref (CNL-0023)"
            )
        for _ in range(count):
            out.append(
                {
                    "provenance_ref": provenance_ref,
                    "ranking": ranking,
                    "weight": weight,
                }
            )
    return out


def pairwise_matrix(
    candidates: list[str], ballots: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    matrix = {a: {b: 0 for b in candidates} for a in candidates}
    rank_of = []
    for ball in ballots:
        ranking = ball["ranking"]
        missing = [c for c in candidates if c not in ranking]
        if missing:
            raise SpecError(f"ballot ranking omits {missing}")
        extra = [c for c in ranking if c not in candidates]
        if extra:
            raise SpecError(f"ballot ranking has unknown {extra}")
        rank_of.append({c: i for i, c in enumerate(ranking)})
    for ball, ranks in zip(ballots, rank_of):
        w = int(ball["weight"])
        for a in candidates:
            for b in candidates:
                if a == b:
                    continue
                if ranks[a] < ranks[b]:
                    matrix[a][b] += w
    return matrix


def majority_beats(
    matrix: dict[str, dict[str, int]], a: str, b: str
) -> bool:
    return matrix[a][b] > matrix[b][a]


def condorcet_winner(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> str | None:
    for a in candidates:
        if all(majority_beats(matrix, a, b) for b in candidates if b != a):
            return a
    return None


def _majority_graph(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> dict[str, list[str]]:
    edges = {c: [] for c in candidates}
    for a in candidates:
        for b in candidates:
            if a != b and majority_beats(matrix, a, b):
                edges[a].append(b)
    return edges


def smith_set(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> list[str]:
    edges = _majority_graph(matrix, candidates)
    rev = {c: [] for c in candidates}
    for u, vs in edges.items():
        for v in vs:
            rev[v].append(u)
    seen: set[str] = set()
    order: list[str] = []

    def dfs(u: str, graph: dict[str, list[str]], acc: list[str]) -> None:
        seen.add(u)
        for v in graph[u]:
            if v not in seen:
                dfs(v, graph, acc)
        acc.append(u)

    for c in candidates:
        if c not in seen:
            dfs(c, edges, order)
    seen.clear()
    components: list[list[str]] = []
    for u in reversed(order):
        if u not in seen:
            comp: list[str] = []
            dfs(u, rev, comp)
            components.append(comp)
    cid = {v: i for i, comp in enumerate(components) for v in comp}
    inbound = {i: 0 for i in range(len(components))}
    for u, vs in edges.items():
        for v in vs:
            if cid[u] != cid[v]:
                inbound[cid[v]] += 1
    sources = [i for i, n in inbound.items() if n == 0]
    smith: list[str] = []
    for i in sources:
        smith.extend(components[i])
    order_index = {c: i for i, c in enumerate(candidates)}
    smith.sort(key=lambda c: order_index[c])
    return smith


def schulze_paths(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> dict[str, dict[str, int]]:
    p = {a: {b: 0 for b in candidates} for a in candidates}
    for a in candidates:
        for b in candidates:
            if a == b:
                continue
            if matrix[a][b] > matrix[b][a]:
                p[a][b] = matrix[a][b]
    for k in candidates:
        for i in candidates:
            for j in candidates:
                if i == j:
                    continue
                via = min(p[i][k], p[k][j])
                if via > p[i][j]:
                    p[i][j] = via
    return p


def schulze_winner(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> str:
    p = schulze_paths(matrix, candidates)
    scores = {a: 0 for a in candidates}
    for a in candidates:
        for b in candidates:
            if a != b and p[a][b] > p[b][a]:
                scores[a] += 1
    best = max(scores.values())
    tied = [c for c in candidates if scores[c] == best]
    return tied[0]


def plurality_in_smith_winner(
    matrix: dict[str, dict[str, int]],
    candidates: list[str],
    ballots: list[dict[str, Any]],
) -> str:
    smith = smith_set(matrix, candidates)
    smith_set_ids = set(smith)
    tallies = {c: 0 for c in smith}
    for ball in ballots:
        w = int(ball["weight"])
        for c in ball["ranking"]:
            if c in smith_set_ids:
                tallies[c] += w
                break
    best = max(tallies.values())
    tied = [c for c in smith if tallies[c] == best]
    return tied[0]


def minimax_winning_votes_winner(
    matrix: dict[str, dict[str, int]], candidates: list[str]
) -> str:
    worst = {}
    for a in candidates:
        losses = [matrix[b][a] for b in candidates if b != a and matrix[b][a] > matrix[a][b]]
        worst[a] = max(losses) if losses else 0
    best = min(worst.values())
    tied = [c for c in candidates if worst[c] == best]
    return tied[0]


def apply_completion(
    rule: str,
    matrix: dict[str, dict[str, int]],
    candidates: list[str],
    ballots: list[dict[str, Any]],
) -> str:
    if rule == "schulze":
        return schulze_winner(matrix, candidates)
    if rule == "plurality_in_smith":
        return plurality_in_smith_winner(matrix, candidates, ballots)
    if rule == "minimax_winning_votes":
        return minimax_winning_votes_winner(matrix, candidates)
    raise SpecError(f"unknown cycle_completion={rule!r}")


def ingest_and_tabulate(spec: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    if spec.get("ingested"):
        raise SpecError("ballots already ingested; spec is frozen")
    expected = freeze_token(spec["cycle_completion"], spec["candidate_order"])
    if spec.get("freeze_token") != expected:
        raise SpecError("freeze_token does not match declared cycle_completion")
    candidates = list(spec["candidate_order"])
    ballots = expand_ballots(rows)
    matrix = pairwise_matrix(candidates, ballots)
    cw = condorcet_winner(matrix, candidates)
    smith = smith_set(matrix, candidates)
    cycle = cw is None
    if cycle:
        winner = apply_completion(
            spec["cycle_completion"], matrix, candidates, ballots
        )
        completion_used = spec["cycle_completion"]
    else:
        winner = cw
        completion_used = None
    spec["ingested"] = True
    return {
        "candidate_order": candidates,
        "completion_used": completion_used,
        "condorcet_winner": cw,
        "cycle_detected": cycle,
        "cycle_completion_declared": spec["cycle_completion"],
        "freeze_token": spec["freeze_token"],
        "pairwise": matrix,
        "smith_set": smith,
        "winner": winner,
    }


def rebind_after_ingest(spec: dict[str, Any], new_rule: str) -> dict[str, Any]:
    if not spec.get("ingested"):
        spec["cycle_completion"] = new_rule
        spec["freeze_token"] = freeze_token(new_rule, spec["candidate_order"])
        return {"ok": True, "reason": "rebind-allowed-before-ingest"}
    return {
        "ok": False,
        "reason": "cycle_completion frozen after ballot ingest",
        "declared": spec["cycle_completion"],
        "rejected": new_rule,
        "freeze_token": spec["freeze_token"],
    }


def tabulate_with_rule(
    candidate_order: list[str],
    rows: list[dict[str, Any]],
    rule: str,
) -> dict[str, Any]:
    """Tabulate as if `rule` had been the frozen declaration. Does not mutate freeze."""
    spec = freeze_spec(rule, candidate_order)
    return ingest_and_tabulate(spec, rows)
