"""Marketplace dependency graph: kinds, publish-time cycle gate, install order."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

KIND_REQUIRED = "required"
KIND_OPTIONAL = "optional"
KIND_PEER = "peer"
KIND_DEV = "dev"
KIND_ORDER = (KIND_REQUIRED, KIND_OPTIONAL, KIND_PEER, KIND_DEV)
INSTALL_KINDS = frozenset({KIND_REQUIRED})


class DependencyCycleError(Exception):
    def __init__(self, path: Sequence[str], stage: str = "publish") -> None:
        self.path = list(path)
        self.stage = stage
        pretty = " -> ".join(self.path)
        super().__init__(f"dependency cycle at {stage}: {pretty}")


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str
    range: str


@dataclass(frozen=True)
class Cycle:
    path: tuple[str, ...]


@dataclass
class Graph:
    nodes: set[str] = field(default_factory=set)
    edges: list[Edge] = field(default_factory=list)

    def pair_list(self, kinds: Iterable[str] | None = None) -> list[tuple[str, str]]:
        allow = set(kinds) if kinds is not None else {e.kind for e in self.edges}
        return [(e.src, e.dst) for e in self.edges if e.kind in allow]

    def classify(self) -> dict[str, list[tuple[str, str, str]]]:
        out: dict[str, list[tuple[str, str, str]]] = {k: [] for k in KIND_ORDER}
        for e in self.edges:
            out.setdefault(e.kind, []).append((e.src, e.dst, e.range))
        for k in out:
            out[k].sort()
        return out

    def successors(self, kinds: Iterable[str] | None = None) -> dict[str, list[str]]:
        allow = set(kinds) if kinds is not None else INSTALL_KINDS
        succ: dict[str, list[str]] = {n: [] for n in self.nodes}
        for e in self.edges:
            if e.kind in allow:
                succ.setdefault(e.src, []).append(e.dst)
                succ.setdefault(e.dst, [])
        return succ


def graph_from_document(doc: dict[str, Any]) -> Graph:
    g = Graph()
    packages = doc.get("packages") or {}
    for name, body in packages.items():
        g.nodes.add(str(name))
        deps = (body or {}).get("dependencies") or {}
        for kind in KIND_ORDER:
            block = deps.get(kind) or {}
            if isinstance(block, dict):
                for dest, rng in block.items():
                    g.nodes.add(str(dest))
                    g.edges.append(
                        Edge(str(name), str(dest), kind, str(rng if rng is not None else "*"))
                    )
    return g


def _simple_cycles(succ: dict[str, list[str]]) -> list[Cycle]:
    """Johnson-style simple directed cycles; path is closed (first==last)."""
    found: list[Cycle] = []
    nodes = sorted(succ)
    adj = {n: list(dict.fromkeys(succ.get(n) or [])) for n in nodes}

    def circuit(start: str, path: list[str], blocked: set[str]) -> None:
        node = path[-1]
        for nxt in adj.get(node, []):
            if nxt < start:
                continue
            if nxt == start:
                found.append(Cycle(tuple(path + [start])))
            elif nxt not in blocked and nxt not in path:
                blocked.add(nxt)
                circuit(start, path + [nxt], blocked)
                blocked.discard(nxt)

    for start in nodes:
        circuit(start, [start], {start})

    # Dedup rotations of the same cycle (keep closed path starting at min interior node
    # that preserves original edge order from that node).
    uniq: dict[tuple[str, ...], Cycle] = {}
    for cyc in found:
        body = list(cyc.path[:-1])
        if not body:
            continue
        k = body.index(min(body))
        rot = body[k:] + body[:k] + [body[k]]
        key = tuple(rot)
        uniq[key] = Cycle(key)
    return [uniq[k] for k in sorted(uniq)]


def detect_cycles(graph: Graph, kinds: Iterable[str] | None = None) -> list[Cycle]:
    allow = tuple(kinds) if kinds is not None else (KIND_REQUIRED,)
    return _simple_cycles(graph.successors(allow))


def cycle_matches(found: Sequence[Cycle], expected: Sequence[Sequence[str]]) -> bool:
    got = [list(c.path) for c in found]
    want = [list(p) for p in expected]
    return got == want


def membership(found: Sequence[Cycle]) -> set[str]:
    names: set[str] = set()
    for c in found:
        names.update(c.path)
    return names


def check_at_publish(graph: Graph) -> dict[str, Any]:
    cycles = detect_cycles(graph)
    if cycles:
        raise DependencyCycleError(cycles[0].path, stage="publish")
    return {"ok": True, "stage": "publish", "cycles": []}


def publish_verdict(graph: Graph) -> dict[str, Any]:
    cycles = detect_cycles(graph)
    if not cycles:
        return {"ok": True, "stage": "publish", "cycles": []}
    return {
        "ok": False,
        "stage": "publish",
        "cycles": [list(c.path) for c in cycles],
        "error": str(DependencyCycleError(cycles[0].path, stage="publish")),
    }


def install_order(graph: Graph) -> list[str]:
    cycles = detect_cycles(graph)
    if cycles:
        raise DependencyCycleError(cycles[0].path, stage="install")
    succ = graph.successors(INSTALL_KINDS)
    indeg: dict[str, int] = {n: 0 for n in graph.nodes}
    for src, dsts in succ.items():
        for dst in dsts:
            indeg.setdefault(dst, 0)
            indeg[dst] += 1
            indeg.setdefault(src, 0)
    q = deque(sorted(n for n, d in indeg.items() if d == 0))
    out: list[str] = []
    while q:
        n = q.popleft()
        out.append(n)
        for dst in succ.get(n, []):
            indeg[dst] -= 1
            if indeg[dst] == 0:
                q.append(dst)
        q = deque(sorted(q))
    if len(out) != len(indeg):
        raise DependencyCycleError(["?"], stage="install")
    return out


def naive_recursive_walk(graph: Graph, start: str) -> None:
    """Deliberately recursive walker — RecursionError is the dead control."""
    for nxt in graph.successors(INSTALL_KINDS).get(start) or []:
        naive_recursive_walk(graph, nxt)
