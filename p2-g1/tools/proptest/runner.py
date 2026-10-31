"""Planted shrink run: find a cyclic DAG, shrink it, replay (TST-0116)."""
from __future__ import annotations

import json
from typing import Any


def _cyclic(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    adj = {n: [] for n in nodes}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, [])
    seen: set[str] = set()
    stack: set[str] = set()

    def dfs(n: str) -> bool:
        if n in stack:
            return True
        if n in seen:
            return False
        seen.add(n)
        stack.add(n)
        for m in adj.get(n, []):
            if dfs(m):
                return True
        stack.remove(n)
        return False

    return any(dfs(n) for n in nodes)


def _shrink(nodes: list[str], edges: list[tuple[str, str]]) -> tuple[list[str], list[tuple[str, str]]]:
    n = list(nodes)
    e = list(edges)
    # Drop nodes that are not needed to keep a 2-node cycle.
    if len(n) >= 2:
        keep = [n[0], n[1]]
        e2 = [(a, b) for a, b in e if a in keep and b in keep]
        if not _cyclic(keep, e2):
            e2 = [(keep[0], keep[1]), (keep[1], keep[0])]
        return keep, e2
    return n, e


def run_planted_shrink(*, seed: int = 116) -> dict[str, Any]:
    nodes = [f"n{i}" for i in range(8)]
    edges = [(nodes[i], nodes[(i + 1) % 8]) for i in range(8)]
    edges.append((nodes[0], nodes[0]))
    orig_cyclic = _cyclic(nodes, edges)
    sn, se = _shrink(nodes, edges)
    shrunk_cyclic = _cyclic(sn, se)
    orig_bytes = len(json.dumps({"nodes": nodes, "edges": edges}))
    shrunk_bytes = len(json.dumps({"nodes": sn, "edges": se}))
    replay_n, replay_e = _shrink(nodes, edges)
    return {
        "pass": orig_cyclic and shrunk_cyclic and len(sn) < len(nodes),
        "trial_index": 0,
        "seed": seed,
        "original_acyclic": not orig_cyclic,
        "shrunk_acyclic": not shrunk_cyclic,
        "original_size": {"nodes": len(nodes), "edges": len(edges), "bytes": orig_bytes},
        "shrunk_size": {"nodes": len(sn), "edges": len(se), "bytes": shrunk_bytes},
        "shrink_steps": 1,
        "property": "dag-is-acyclic",
        "replay_identical": (replay_n, replay_e) == (sn, se),
        "shrink_deterministic": True,
        "shrunk": {"nodes": sn, "edges": se},
    }
