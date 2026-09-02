#!/usr/bin/env python3
"""Independent recomputation of ranking from a published pairwise matrix.

Does not read raw scorecards. Implements Copeland, Schulze, and cycle
detection on the matrix alone so a reviewer can recompute the winner.
"""
from __future__ import annotations

from collections import defaultdict


def majority_graph(pairs: list[dict], entries: list[str]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    known = set(entries)
    for p in pairs:
        a, b = str(p.get("a") or ""), str(p.get("b") or "")
        if a not in known or b not in known:
            continue
        av, bv = int(p.get("a_votes") or 0), int(p.get("b_votes") or 0)
        if av > bv:
            graph[a].add(b)
        elif bv > av:
            graph[b].add(a)
    return graph


def condorcet_winner(entries: list[str], graph: dict[str, set[str]]) -> str | None:
    hits = []
    for e in entries:
        others = set(entries) - {e}
        if others and others <= graph.get(e, set()):
            hits.append(e)
    return hits[0] if len(hits) == 1 else None


def cycles(entries: list[str], graph: dict[str, set[str]]) -> list[list[str]]:
    found: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def canon(path: list[str]) -> tuple[str, ...]:
        n = len(path)
        rot = min(range(n), key=lambda i: path[i])
        fwd = path[rot:] + path[:rot]
        rev = list(reversed(path))
        rot_r = min(range(n), key=lambda i: rev[i])
        bwd = rev[rot_r:] + rev[:rot_r]
        pick = fwd if tuple(fwd) <= tuple(bwd) else bwd
        return tuple(pick)

    def dfs(start: str, node: str, path: list[str], stack: set[str]) -> None:
        for nxt in sorted(graph.get(node, ())):
            if nxt == start and len(path) >= 3:
                c = canon(path)
                if c not in seen:
                    seen.add(c)
                    found.append(list(c))
            elif nxt not in stack and nxt >= start:
                stack.add(nxt)
                path.append(nxt)
                dfs(start, nxt, path, stack)
                path.pop()
                stack.remove(nxt)

    for start in entries:
        dfs(start, start, [start], {start})
    found.sort(key=lambda c: (len(c), c))
    return found


def copeland(entries: list[str], pairs: list[dict]) -> dict[str, int]:
    scores = {e: 0 for e in entries}
    known = set(entries)
    for p in pairs:
        a, b = str(p.get("a") or ""), str(p.get("b") or "")
        if a not in known or b not in known:
            continue
        av, bv = int(p.get("a_votes") or 0), int(p.get("b_votes") or 0)
        if av > bv:
            scores[a] += 1
            scores[b] -= 1
        elif bv > av:
            scores[b] += 1
            scores[a] -= 1
    return scores


def schulze(entries: list[str], pairs: list[dict]) -> dict[str, tuple[int, int]]:
    idx = {e: i for i, e in enumerate(entries)}
    n = len(entries)
    d = [[0] * n for _ in range(n)]
    for p in pairs:
        a, b = str(p.get("a") or ""), str(p.get("b") or "")
        if a not in idx or b not in idx:
            continue
        i, j = idx[a], idx[b]
        av, bv = int(p.get("a_votes") or 0), int(p.get("b_votes") or 0)
        if av > bv:
            d[i][j] = av
        elif bv > av:
            d[j][i] = bv
    pth = [row[:] for row in d]
    for k in range(n):
        for i in range(n):
            if i == k:
                continue
            for j in range(n):
                if j == i or j == k:
                    continue
                pth[i][j] = max(pth[i][j], min(pth[i][k], pth[k][j]))
    out: dict[str, tuple[int, int]] = {}
    for i, a in enumerate(entries):
        wins = 0
        strength = 0
        for j, b in enumerate(entries):
            if i == j:
                continue
            if pth[i][j] > pth[j][i]:
                wins += 1
            strength += pth[i][j] - pth[j][i]
        out[a] = (wins, strength)
    return out


def rank_from_matrix(
    pairs: list[dict],
    entries: list[str],
    evidence_totals: dict[str, float] | None = None,
) -> dict:
    """Reproduce ranking from the published matrix (+ optional published totals)."""
    ev = {e: float((evidence_totals or {}).get(e) or 0.0) for e in entries}
    graph = majority_graph(pairs, entries)
    unique = condorcet_winner(entries, graph)
    cop = copeland(entries, pairs)
    sch = schulze(entries, pairs)
    cyc = cycles(entries, graph)

    def key(e: str) -> tuple:
        sw, ss = sch[e]
        return (
            0 if e == unique else 1,
            -cop[e],
            -sw,
            -ss,
            -ev[e],
            e,
        )

    order = sorted(entries, key=key)
    return {
        "condorcet_winner": unique,
        "cycles": cyc,
        "ranking": order,
        "copeland": cop,
        "tie_break_applied": unique is None,
    }
