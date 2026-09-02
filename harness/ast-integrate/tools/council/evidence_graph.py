"""Cycle detection over the council evidence graph (circular citation).

A council's claims, evidence and contradictions form a directed graph. A
*support* edge ``A -> B`` says "A is supported by B". A claim that is
ultimately supported only by itself through intermediaries closes a support
cycle, and that is circular citation: the argument has no root in evidence.

:func:`inspect` walks the support edges only (contradiction edges are a
different relation and a contradiction pair is legitimately mutual), prints
the full node path of every cycle it finds, and reports the graph size so a
zero-cycle result is distinguishable from an empty graph. An empty support
graph is ``NOT-CHECKED`` and never ``accepted``: nothing was verified, so
nothing may be claimed. A diamond (long chains sharing an ancestor) is a DAG
and stays silent; only a directed closed walk fires.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from typing import Any

STATUS_CYCLIC = "CYCLIC"
STATUS_ACYCLIC = "ACYCLIC"
STATUS_NOT_CHECKED = "NOT-CHECKED"
PATH_SEPARATOR = " -> "


class EvidenceGraphError(ValueError):
    """Base class for evidence-graph refusals."""


class CyclicEvidenceError(EvidenceGraphError):
    """The support graph closes at least one cycle."""


class EmptyEvidenceError(EvidenceGraphError):
    """The support graph has no edges, so nothing was checked."""


def _edge_pairs(edges: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for e in edges or []:
        if isinstance(e, Mapping):
            src, dst = e.get("from"), e.get("to")
        elif isinstance(e, (list, tuple)) and len(e) == 2:
            src, dst = e
        else:
            raise EvidenceGraphError(f"edge {e!r} is neither a mapping nor a pair")
        if src is None or dst is None:
            raise EvidenceGraphError(f"edge {e!r} is missing an endpoint")
        out.append((str(src), str(dst)))
    return out


def _node_ids(graph: Mapping[str, Any], edges: Iterable[tuple[str, str]]) -> list[str]:
    """Declared nodes first, in declaration order, then any endpoint that was
    only mentioned by an edge."""
    ordered: list[str] = []
    seen: set[str] = set()
    for n in graph.get("nodes") or []:
        nid = n.get("id") if isinstance(n, Mapping) else n
        if nid is None:
            raise EvidenceGraphError(f"node {n!r} has no id")
        nid = str(nid)
        if nid not in seen:
            seen.add(nid)
            ordered.append(nid)
    for src, dst in edges:
        for nid in (src, dst):
            if nid not in seen:
                seen.add(nid)
                ordered.append(nid)
    return ordered


def format_path(path: Iterable[str]) -> str:
    return PATH_SEPARATOR.join(path)


def kahn_leftover(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[str]:
    """Nodes that Kahn's algorithm cannot order: exactly the nodes on or
    downstream-locked behind a cycle. Empty for a DAG."""
    node_list = list(nodes)
    indeg = {n: 0 for n in node_list}
    out: dict[str, list[str]] = {n: [] for n in node_list}
    for src, dst in edges:
        out[src].append(dst)
        indeg[dst] += 1
    queue = deque(n for n in node_list if indeg[n] == 0)
    removed: set[str] = set()
    while queue:
        n = queue.popleft()
        removed.add(n)
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return [n for n in node_list if n not in removed]


def find_cycles(
    nodes: Iterable[str], edges: Iterable[tuple[str, str]]
) -> list[list[str]]:
    """Every elementary directed cycle reachable by DFS in node order.

    Each cycle is returned as a closed path (first node repeated at the end),
    starting at the first node of the cycle that the walk entered, so the
    printed path is deterministic for a given node/edge order.
    """
    node_list = list(nodes)
    adj: dict[str, list[str]] = {n: [] for n in node_list}
    for src, dst in edges:
        adj[src].append(dst)

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in node_list}
    cycles: list[list[str]] = []
    seen_cycles: set[tuple[str, ...]] = set()
    stack: list[str] = []

    def visit(n: str) -> None:
        colour[n] = GREY
        stack.append(n)
        for m in adj[n]:
            if colour[m] == GREY:
                start = stack.index(m)
                cycle = stack[start:] + [m]
                key = tuple(sorted(set(cycle)))
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    cycles.append(cycle)
            elif colour[m] == WHITE:
                visit(m)
        stack.pop()
        colour[n] = BLACK

    for n in node_list:
        if colour[n] == WHITE:
            visit(n)
    return cycles


def inspect(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Inspect a council graph for circular citation.

    Returns a report with ``status`` (``CYCLIC`` / ``ACYCLIC`` /
    ``NOT-CHECKED``), every cycle as ``{"path": [...], "path_printed": "a -> b -> a"}``,
    the Kahn leftover, the graph size and whether the graph is ``accepted``.
    """
    if not isinstance(graph, Mapping):
        raise EvidenceGraphError(f"graph must be a mapping, got {type(graph).__name__}")
    support = _edge_pairs(graph.get("support_edges"))
    contradictions = _edge_pairs(graph.get("contradiction_edges"))
    nodes = _node_ids(graph, [*support, *contradictions])
    size = {
        "nodes": len(nodes),
        "edges": len(support),
        "contradiction_edges": len(contradictions),
    }

    if not support:
        return {
            "status": STATUS_NOT_CHECKED,
            "accepted": False,
            "reason": "no support edges: nothing was checked, nothing may be claimed",
            "cycles": [],
            "cycle_count": 0,
            "kahn_leftover": [],
            "graph_size": size,
            "nodes": nodes,
            "support_edges": [],
            "contradiction_edges": [{"from": a, "to": b} for a, b in contradictions],
        }

    cycles = find_cycles(nodes, support)
    leftover = kahn_leftover(nodes, support)
    cyclic = bool(cycles) or bool(leftover)
    return {
        "status": STATUS_CYCLIC if cyclic else STATUS_ACYCLIC,
        "accepted": not cyclic,
        "reason": (
            f"{len(cycles)} support cycle(s) close on themselves"
            if cyclic
            else "support graph is a DAG"
        ),
        "cycles": [
            {"path": list(c), "path_printed": format_path(c), "length": len(c) - 1}
            for c in cycles
        ],
        "cycle_count": len(cycles),
        "kahn_leftover": leftover,
        "graph_size": size,
        "nodes": nodes,
        "support_edges": [{"from": a, "to": b} for a, b in support],
        "contradiction_edges": [{"from": a, "to": b} for a, b in contradictions],
    }


def enforce(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Like :func:`inspect` but refuses instead of reporting: raises
    :class:`CyclicEvidenceError` on a cycle and :class:`EmptyEvidenceError`
    when there was nothing to check."""
    report = inspect(graph)
    if report["status"] == STATUS_CYCLIC:
        printed = "; ".join(c["path_printed"] for c in report["cycles"]) or ",".join(
            report["kahn_leftover"]
        )
        raise CyclicEvidenceError(f"circular citation: {printed}")
    if report["status"] == STATUS_NOT_CHECKED:
        raise EmptyEvidenceError("empty support graph: nothing checked")
    return report


__all__ = [
    "PATH_SEPARATOR",
    "STATUS_ACYCLIC",
    "STATUS_CYCLIC",
    "STATUS_NOT_CHECKED",
    "CyclicEvidenceError",
    "EmptyEvidenceError",
    "EvidenceGraphError",
    "enforce",
    "find_cycles",
    "format_path",
    "inspect",
    "kahn_leftover",
]
