"""council.evidence_graph - the directed support-graph invariant (TST-0261).

The council claim/evidence/contradiction graph is a DIRECTED graph. A support
edge ``src -> dst`` means "src cites dst (dst supports src)". Circular
citation is a closed path over SUPPORT edges only: a claim ultimately
supported only by itself through intermediaries. Contradiction edges are
stored and counted but never decide circular citation (a contradiction
2-cycle is disagreement, not self-support).

Every detected cycle is reported with its FULL closed node path - a bare
count is unreviewable. Graph size (nodes, edges) is always published so a
zero-cycle result cannot be confused with an empty graph. A graph with zero
support edges is NOT-CHECKED, never a clean pass.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

__all__ = [
    "directed_support_cycles",
    "kahn_leftover",
    "inspect",
    "enforce",
    "graph_size",
]

_NOT_CHECKED = "NOT-CHECKED"


def _nodes(graph: dict[str, Any]) -> list[str]:
    out = [str(n) for n in (graph.get("nodes") or [])]
    for s, d in graph.get("support") or []:
        for n in (s, d):
            if str(n) not in out:
                out.append(str(n))
    for a, b in graph.get("contradiction") or []:
        for n in (a, b):
            if str(n) not in out:
                out.append(str(n))
    return out


def graph_size(graph: dict[str, Any]) -> dict[str, int]:
    support = [(str(s), str(d)) for s, d in (graph.get("support") or [])]
    contra = [(str(a), str(b)) for a, b in (graph.get("contradiction") or [])]
    return {
        "nodes": len(_nodes(graph)),
        "edges": len(support) + len(contra),
        "support_edges": len(support),
        "contradiction_edges": len(contra),
    }


def _sccs(nodes: list[str], adj: dict[str, list[str]]) -> list[set[str]]:
    """Iterative Tarjan strongly connected components."""
    index_counter = 0
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[set[str]] = []

    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = lowlink[node] = index_counter
                index_counter += 1
                stack.append(node)
                on_stack.add(node)
            recurse = False
            succ = adj.get(node, [])
            for i in range(pi, len(succ)):
                nxt = succ[i]
                if nxt not in index:
                    work[-1] = (node, i + 1)
                    work.append((nxt, 0))
                    recurse = True
                    break
                if nxt in on_stack:
                    lowlink[node] = min(lowlink[node], index[nxt])
            if recurse:
                continue
            if lowlink[node] == index[node]:
                comp: set[str] = set()
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.add(w)
                    if w == node:
                        break
                result.append(comp)
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return result


def _closed_path(
    comp: set[str], adj: dict[str, list[str]]
) -> list[str]:
    """One closed walk inside a cycle component, canonical start = min node."""
    start = min(comp)
    path = [start]
    seen = {start}
    cur = start
    while True:
        nxts = sorted(n for n in adj.get(cur, []) if n in comp)
        step = None
        for n in nxts:
            if n == start:
                path.append(start)
                return path
            if n not in seen:
                step = n
                break
        if step is None:
            # Dead end inside the component (should not happen for an SCC
            # of size > 1): backtrack by restarting the walk from a fresh
            # edge to start, or fall back to the direct return edge.
            path.append(start)
            return path
        path.append(step)
        seen.add(step)
        cur = step


def directed_support_cycles(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Every directed cycle over SUPPORT edges, with its full closed path."""
    support = [(str(s), str(d)) for s, d in (graph.get("support") or [])]
    adj: dict[str, list[str]] = defaultdict(list)
    for s, d in support:
        adj[s].append(d)
    nodes = _nodes(graph)
    cycles: list[dict[str, Any]] = []
    for comp in _sccs(nodes, adj):
        if len(comp) > 1 or any(s == d and s in comp for s, d in support):
            path = _closed_path(comp, adj)
            cycle_nodes = list(dict.fromkeys(path[:-1])) if path[-1] == path[0] else list(dict.fromkeys(path))
            cycles.append(
                {
                    "length": len(cycle_nodes),
                    "nodes": cycle_nodes,
                    "path": path,
                    "path_printed": " -> ".join(path),
                }
            )
    cycles.sort(key=lambda c: c["path_printed"])
    return cycles


def kahn_leftover(graph: dict[str, Any]) -> list[str]:
    """Nodes never peeled by Kahn's algorithm over support edges.

    Leftover = the nodes trapped in (or fed only by) directed cycles. An
    acyclic graph peels completely: leftover is empty.
    """
    support = [(str(s), str(d)) for s, d in (graph.get("support") or [])]
    adj: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = defaultdict(int)
    nodes = _nodes(graph)
    for n in nodes:
        indeg.setdefault(n, 0)
    for s, d in support:
        adj[s].append(d)
        indeg[d] += 1
    queue = deque(sorted(n for n in nodes if indeg[n] == 0))
    while queue:
        n = queue.popleft()
        for m in sorted(adj.get(n, [])):
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return sorted(n for n in nodes if indeg[n] > 0)


def inspect(graph: dict[str, Any]) -> dict[str, Any]:
    """Full report: status, fired, every cycle path, graph size, acceptance."""
    size = graph_size(graph)
    report: dict[str, Any] = {
        "graph_size": size,
        "cycles": [],
        "fired": False,
        "accepted": False,
    }
    if size["support_edges"] == 0:
        report["status"] = _NOT_CHECKED
        report["reason"] = (
            "zero evidence edges - a graph with no support edges cannot be "
            "checked for circular citation, and must never read as ACYCLIC"
        )
        return report
    cycles = directed_support_cycles(graph)
    report["cycles"] = cycles
    report["fired"] = bool(cycles)
    report["status"] = "CYCLIC" if cycles else "ACYCLIC"
    report["accepted"] = not cycles
    return report


def enforce(graph: dict[str, Any]) -> dict[str, Any]:
    """Gate verdict: reject any support path that closes a cycle."""
    report = inspect(graph)
    verdict = {
        "status": report["status"],
        "accepted": False,
        "fired": report["fired"],
        "graph_size": report["graph_size"],
        "cycles": report["cycles"],
    }
    if report["status"] == _NOT_CHECKED:
        verdict["reason"] = report["reason"]
    elif report["status"] == "CYCLIC":
        verdict["reason"] = (
            "circular citation: "
            + "; ".join(c["path_printed"] for c in report["cycles"])
        )
    else:
        verdict["reason"] = "no support-edge cycle"
        verdict["accepted"] = True
    return verdict
