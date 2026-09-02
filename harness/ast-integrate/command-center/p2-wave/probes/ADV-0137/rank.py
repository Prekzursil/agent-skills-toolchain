"""Transitive load-bearing rank along unit-id dependency edges."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable


def reverse_unit_edges(dependencies: dict[str, list[str]]) -> dict[str, set[str]]:
    idset = set(dependencies)
    rev: dict[str, set[str]] = defaultdict(set)
    for uid, deps in dependencies.items():
        for tok in deps:
            if tok in idset:
                rev[tok].add(uid)
    return rev


def reach(starts: Iterable[str], rev: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    dq: deque[str] = deque(starts)
    while dq:
        x = dq.popleft()
        if x in seen:
            continue
        seen.add(x)
        for y in rev.get(x, ()):
            if y not in seen:
                dq.append(y)
    return seen


def ranks_for_histogram(
    unit_sources: dict[str, list[str]],
    dependencies: dict[str, list[str]],
) -> dict[str, dict]:
    rev = reverse_unit_edges(dependencies)
    by_source: dict[str, list[str]] = defaultdict(list)
    for uid, srcs in unit_sources.items():
        for s in srcs:
            by_source[s].append(uid)
    out: dict[str, dict] = {}
    for source, direct in by_source.items():
        trans = reach(direct, rev)
        out[source] = {
            "source": source,
            "direct_units": len(direct),
            "rank": len(trans),
        }
    return out
