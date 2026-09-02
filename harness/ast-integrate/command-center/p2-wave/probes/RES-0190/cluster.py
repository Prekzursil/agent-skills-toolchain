"""Mechanism-level clustering: union-find on mechanism_dedup MERGE only."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from mechanism_dedup import compare  # noqa: E402


def _find(parent: list[int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: list[int], a: int, b: int) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def cluster_labels(texts: list[str]) -> list[int]:
    n = len(texts)
    parent = list(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            row = compare(texts[i], texts[j])
            if row.get("verdict") == "MERGE":
                _union(parent, i, j)
    return [_find(parent, i) for i in range(n)]


def distinct_count(texts: Iterable[str]) -> int:
    items = [t for t in texts if isinstance(t, str) and t.strip()]
    if not items:
        return 0
    return len(set(cluster_labels(items)))


def pair_verdict(a: str, b: str) -> dict:
    return compare(a, b)
