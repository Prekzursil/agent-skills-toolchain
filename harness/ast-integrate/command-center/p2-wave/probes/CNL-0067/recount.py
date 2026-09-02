#!/usr/bin/env python3
"""Independent recount: Kahn leftover vs DFS cycles, and a second weight walk.

Probe 2 must not trust delegate.find_cycles / delegate.resolve_weights numbers.
This module re-derives cycle membership and terminal weights from the fixture.
"""
from __future__ import annotations

from collections import deque
from typing import Any


def kahn_cyclic_nodes(profile: dict[str, Any]) -> set[str]:
    nodes = [str(r["id"]) for r in profile["seats"]]
    known = set(nodes)
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    indeg = {n: 0 for n in nodes}
    for row in profile["seats"]:
        src = str(row["id"])
        tgt = row.get("delegates_to")
        if tgt is None or tgt == "":
            continue
        tgt = str(tgt)
        if tgt not in known:
            continue
        succ[src].append(tgt)
        indeg[tgt] += 1
    q = deque(n for n in nodes if indeg[n] == 0)
    peeled = 0
    while q:
        n = q.popleft()
        peeled += 1
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if peeled == len(nodes):
        return set()
    return {n for n in nodes if indeg[n] > 0}


def independent_effective(profile: dict[str, Any]) -> dict[str, float]:
    """Walk each seat to its terminal; error if a cycle is encountered."""
    ed: dict[str, str] = {}
    base: dict[str, float] = {}
    known = set()
    for row in profile["seats"]:
        sid = str(row["id"])
        known.add(sid)
        base[sid] = float(row.get("base_weight", 1))
        tgt = row.get("delegates_to")
        if tgt not in (None, ""):
            ed[sid] = str(tgt)
    effective = {sid: 0.0 for sid in known}
    for sid, wt in base.items():
        cur = sid
        seen: set[str] = set()
        while cur in ed:
            if cur in seen:
                raise RuntimeError(f"independent walk hit cycle at {cur}")
            seen.add(cur)
            nxt = ed[cur]
            if nxt not in known:
                raise RuntimeError(f"independent walk dangling {nxt}")
            cur = nxt
        effective[cur] += wt
    return effective


def independent_share(effective: dict[str, float], seat: str) -> float:
    total = sum(effective.values())
    if total <= 0:
        return 0.0
    return effective.get(seat, 0.0) / total
