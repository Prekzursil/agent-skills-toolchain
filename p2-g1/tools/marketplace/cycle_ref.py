"""Independent cycle oracles: graphlib.TopologicalSorter + Kosaraju SCC."""
from __future__ import annotations

from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from typing import Iterable, Sequence


def _kosaraju(pairs: Sequence[tuple[str, str]]) -> list[list[str]]:
    nodes: set[str] = set()
    fwd: dict[str, list[str]] = defaultdict(list)
    rev: dict[str, list[str]] = defaultdict(list)
    for a, b in pairs:
        nodes.add(a)
        nodes.add(b)
        fwd[a].append(b)
        rev[b].append(a)
    seen: set[str] = set()
    order: list[str] = []

    def dfs1(n: str) -> None:
        seen.add(n)
        for m in fwd.get(n, []):
            if m not in seen:
                dfs1(m)
        order.append(n)

    for n in sorted(nodes):
        if n not in seen:
            dfs1(n)
    seen.clear()
    sccs: list[list[str]] = []

    def dfs2(n: str, bucket: list[str]) -> None:
        seen.add(n)
        bucket.append(n)
        for m in rev.get(n, []):
            if m not in seen:
                dfs2(m, bucket)

    for n in reversed(order):
        if n not in seen:
            bucket: list[str] = []
            dfs2(n, bucket)
            sccs.append(sorted(bucket))
    return sccs


def independent_report(pairs: Iterable[tuple[str, str]]) -> dict:
    edge_list = [(str(a), str(b)) for a, b in pairs]
    nodes: set[str] = set()
    for a, b in edge_list:
        nodes.add(a)
        nodes.add(b)
    ts = TopologicalSorter()
    for n in nodes:
        ts.add(n)
    for a, b in edge_list:
        ts.add(b, a)
    graphlib_cyclic = False
    try:
        tuple(ts.static_order())
    except CycleError:
        graphlib_cyclic = True
    sccs = _kosaraju(edge_list)
    cyclic_sccs = [s for s in sccs if len(s) > 1 or any(a == b == s[0] for a, b in edge_list)]
    members: list[str] = sorted({n for s in cyclic_sccs for n in s})
    kosaraju_cyclic = bool(members)
    return {
        "graphlib": {"cyclic": graphlib_cyclic},
        "kosaraju": {"cyclic": kosaraju_cyclic, "sccs_cyclic": cyclic_sccs},
        "members": members,
        "internal_existence_agree": graphlib_cyclic == kosaraju_cyclic,
        "independent_existence": graphlib_cyclic,
    }
