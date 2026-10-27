"""Signal A: declared / undirected / asymmetric / dangling counters (WFA-0004)."""
from __future__ import annotations

from typing import Any


def count_graph(adj: dict[str, set[str]]) -> dict[str, Any]:
    nodes = set(adj.keys())
    for targets in adj.values():
        nodes.update(targets)
    declared = 0
    asymmetric = 0
    dangling = 0
    pairs: set[tuple[str, str]] = set()
    for src, targets in adj.items():
        for dst in targets:
            declared += 1
            if dst not in adj and dst not in nodes:
                dangling += 1
            if src not in adj.get(dst, set()):
                asymmetric += 1
            pairs.add((src, dst) if src < dst else (dst, src))
    return {
        "declared": declared,
        "undirected": len(pairs),
        "asymmetric": asymmetric,
        "dangling": dangling,
        "nodes": len(nodes),
    }


__all__ = ["count_graph"]
