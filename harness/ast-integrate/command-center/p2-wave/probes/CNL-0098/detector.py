#!/usr/bin/env python3
"""CNL-0098 structural detectors over a typed council argument graph.

Two independent pathologies, both machine-checkable:

1. Weak synthesis: a synthesis sentence has no inbound SUPPORTS/GROUNDS edge
   from a node reachable from evidence. Counting overlapping tokens is not
   the check; an edge must exist, and its source must be evidence-reachable.

2. Circular citation: a directed cycle on SUPPORTS/CITES/GROUNDS. The
   detector prints the full node path. Distinct URL count is ignored.
   Zero support edges is NOT-CHECKED, never a clean pass.

A diamond DAG is not a cycle. Two documents that cross-reference distinct
facts are not a cycle unless SUPPORTS/CITES/GROUNDS edges close a loop.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

SUPPORT_KINDS = frozenset({"SUPPORTS", "GROUNDS", "CITES"})
EVIDENCE_KINDS = frozenset({"evidence", "observation", "measurement"})
SYNTHESIS_KINDS = frozenset({"synthesis", "sentence"})


def _nodes(doc: dict[str, Any]) -> list[dict[str, Any]]:
    graph = doc.get("argument_graph") or {}
    nodes = list(graph.get("nodes") or [])
    # Synthesis sentences are first-class nodes even if omitted from the graph.
    seen = {n.get("id") for n in nodes if isinstance(n, dict) and n.get("id")}
    for sent in _sentences(doc):
        sid = sent.get("id")
        if sid and sid not in seen:
            nodes.append(
                {
                    "id": sid,
                    "kind": "synthesis",
                    "text": sent.get("text") or "",
                }
            )
            seen.add(sid)
    return [n for n in nodes if isinstance(n, dict) and n.get("id")]


def _edges(doc: dict[str, Any]) -> list[dict[str, Any]]:
    graph = doc.get("argument_graph") or {}
    out = []
    for e in graph.get("edges") or []:
        if not isinstance(e, dict):
            continue
        if e.get("src") and e.get("dst") and e.get("kind"):
            out.append(e)
    return out


def _sentences(doc: dict[str, Any]) -> list[dict[str, Any]]:
    syn = doc.get("synthesis") or {}
    rows = syn.get("sentences") or []
    return [s for s in rows if isinstance(s, dict) and s.get("id")]


def _support_adj(edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if str(e.get("kind") or "") in SUPPORT_KINDS:
            adj[str(e["src"])].append(str(e["dst"]))
    return adj


def _support_edge_count(edges: list[dict[str, Any]]) -> int:
    return sum(1 for e in edges if str(e.get("kind") or "") in SUPPORT_KINDS)


def _evidence_reachable(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> set[str]:
    evid = {
        str(n["id"])
        for n in nodes
        if str(n.get("kind") or "") in EVIDENCE_KINDS
    }
    adj = _support_adj(edges)
    seen: set[str] = set()
    stack = list(evid)
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        for v in adj.get(u, []):
            if v not in seen:
                stack.append(v)
    return seen


def _tarjan_sccs(ids: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    onstack: set[str] = set()
    idx: dict[str, int] = {}
    low: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        idx[v] = index
        low[v] = index
        index += 1
        stack.append(v)
        onstack.add(v)
        for w in adj.get(v, []):
            if w not in idx:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                onstack.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in ids:
        if v not in idx:
            strongconnect(v)
    return sccs


def _normalize_cycle(path: list[str]) -> tuple[str, ...]:
    core = path[:-1] if path and path[0] == path[-1] else list(path)
    if not core:
        return tuple()
    i = min(range(len(core)), key=lambda k: core[k])
    return tuple(core[i:] + core[:i])


def _cycle_in_scc(scc: set[str], adj: dict[str, list[str]]) -> list[str] | None:
    if len(scc) == 1:
        n = next(iter(scc))
        if n in adj.get(n, []):
            return [n, n]
        return None
    start = min(scc)
    stack = [start]
    at = {start: 0}
    parent: dict[str, str | None] = {start: None}
    gray = {start}

    def dfs(u: str) -> list[str] | None:
        for v in adj.get(u, []):
            if v not in scc:
                continue
            if v in gray:
                i = stack.index(v)
                return stack[i:] + [v]
            if v in at:
                continue
            at[v] = len(stack)
            parent[v] = u
            gray.add(v)
            stack.append(v)
            found = dfs(v)
            if found:
                return found
            stack.pop()
            gray.discard(v)
        return None

    return dfs(start)


def find_cycles(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [str(n["id"]) for n in nodes]
    adj = _support_adj(edges)
    found: list[dict[str, Any]] = []
    seen_norm: set[tuple[str, ...]] = set()
    for comp in _tarjan_sccs(ids, adj):
        scc = set(comp)
        self_loop = len(scc) == 1 and comp[0] in adj.get(comp[0], [])
        if len(scc) < 2 and not self_loop:
            continue
        path = _cycle_in_scc(scc, adj)
        if not path:
            continue
        norm = _normalize_cycle(path)
        if not norm or norm in seen_norm:
            continue
        seen_norm.add(norm)
        found.append(
            {
                "path": path,
                "path_str": "->".join(path),
                "scc": sorted(scc),
            }
        )
    found.sort(key=lambda r: r["path_str"])
    return found


def _unindexed_prose(doc: dict[str, Any]) -> bool:
    syn = doc.get("synthesis") or {}
    extra = str(syn.get("preamble") or syn.get("text") or "").strip()
    if not extra:
        return False
    joined = " ".join(str(s.get("text") or "") for s in _sentences(doc)).strip()
    return extra != joined


def analyse(doc: dict[str, Any]) -> dict[str, Any]:
    nodes = _nodes(doc)
    edges = _edges(doc)
    sentences = _sentences(doc)
    node_ids = {str(n["id"]) for n in nodes}
    support_n = _support_edge_count(edges)
    reach = _evidence_reachable(nodes, edges)
    unindexed = _unindexed_prose(doc)

    unsupported: list[str] = []
    if unindexed:
        unsupported.append("unindexed-prose")
    for sent in sentences:
        sid = str(sent["id"])
        inbound = [
            e
            for e in edges
            if str(e.get("dst")) == sid
            and str(e.get("kind") or "") in SUPPORT_KINDS
            and str(e.get("src")) in node_ids
        ]
        if not inbound:
            unsupported.append(sid)
            continue
        srcs = [str(e["src"]) for e in inbound]
        if not any(s in reach for s in srcs):
            unsupported.append(sid)

    cycles = find_cycles(nodes, edges)

    if not sentences and not unindexed:
        weak_status = "NOT-CHECKED"
        weak_fired = False
    elif unsupported:
        weak_status = "FIRE"
        weak_fired = True
    else:
        weak_status = "SILENT"
        weak_fired = False

    if support_n == 0:
        cycle_status = "NOT-CHECKED"
        cycle_fired = False
        # A zero-support graph must not be reported as "no cycles".
        cycles = []
    elif cycles:
        cycle_status = "FIRE"
        cycle_fired = True
    else:
        cycle_status = "SILENT"
        cycle_fired = False

    fired = bool(weak_fired or cycle_fired)
    if fired:
        status = "FIRE"
    elif weak_status == "NOT-CHECKED" and cycle_status == "NOT-CHECKED":
        status = "NOT-CHECKED"
    else:
        status = "SILENT"

    urls = sorted(
        {
            str(n.get("url"))
            for n in nodes
            if n.get("url")
        }
    )
    return {
        "fixture_id": doc.get("fixture_id") or doc.get("id"),
        "nodes": len(nodes),
        "edges": len(edges),
        "support_edges": support_n,
        "synthesis_sentences": len(sentences),
        "unsupported_sentence_ids": unsupported,
        "unindexed_prose": unindexed,
        "cycles": cycles,
        "evidence_reachable_count": len(reach),
        "distinct_urls": urls,
        "distinct_url_count": len(urls),
        "weak_synthesis": {
            "fired": weak_fired,
            "status": weak_status,
            "unsupported_sentence_ids": list(unsupported),
        },
        "circular_citation": {
            "fired": cycle_fired,
            "status": cycle_status,
            "cycles": cycles,
        },
        "fired": fired,
        "status": status,
        "checked": status != "NOT-CHECKED",
    }


def status_line(report: dict[str, Any]) -> str:
    cycles = report.get("cycles") or []
    paths = ",".join(c.get("path_str") or "" for c in cycles) or "-"
    uns = ",".join(report.get("unsupported_sentence_ids") or []) or "-"
    return (
        f"fixture={report.get('fixture_id')} status={report.get('status')} "
        f"weak={report['weak_synthesis']['status']} "
        f"cycle={report['circular_citation']['status']} "
        f"unsupported={uns} cycle_paths={paths} "
        f"nodes={report['nodes']} support_edges={report['support_edges']} "
        f"url_count={report['distinct_url_count']}"
    )
