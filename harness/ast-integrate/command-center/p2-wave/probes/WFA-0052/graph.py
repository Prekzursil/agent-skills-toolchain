"""Needs-graph reconstruction plus two independent topological sorts.

Adapter path: walk the parsed YAML mapping (jobs.*.needs).
Independent path: scan raw YAML text for job-level `needs:` (no mapping walk).
A YAML that merely parses is not a graph proof — the two extractors must agree
and each topo must be a valid linearisation of that edge set.
"""
from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Any

from matrix import normalize_needs


def needs_edges_from_ast(doc: dict) -> tuple[set[str], set[tuple[str, str]]]:
    jobs = doc.get("jobs") if isinstance(doc, dict) else None
    if not isinstance(jobs, dict):
        return set(), set()
    nodes = {str(jid) for jid in jobs}
    edges: set[tuple[str, str]] = set()
    for jid, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for dep in normalize_needs(job.get("needs")):
            if dep not in nodes:
                # dangling need still recorded; topo treats it as an extra node
                nodes.add(dep)
            edges.add((dep, str(jid)))
    return nodes, edges


_JOB_KEY = re.compile(r"^  ([A-Za-z0-9][A-Za-z0-9_-]*):\s*(#.*)?$")
_NEEDS_INLINE = re.compile(r"^    needs:\s*(\[[^\]]*\]|[^#\n]+?)\s*(#.*)?$")
_NEEDS_KEY = re.compile(r"^    needs:\s*(#.*)?$")
_LIST_ITEM = re.compile(r"^    (?:  )?-\s+(\S+)\s*$")


def _parse_needs_value(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw or raw in {">", "|", ">-", "|-"}:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
    return [raw.strip().strip("'\"")]


def needs_edges_from_text(yaml_text: str) -> tuple[set[str], set[tuple[str, str]]]:
    """Line-oriented extractor. Independent of yaml.safe_load mapping walk."""
    lines = yaml_text.replace("\r\n", "\n").split("\n")
    in_jobs = False
    current: str | None = None
    waiting_list = False
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    for line in lines:
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            current = None
            waiting_list = False
            continue
        if in_jobs and line and not line.startswith(" ") and not line.startswith("\t") and line.strip() and not line.strip().startswith("#"):
            # top-level key after jobs — leave jobs block
            in_jobs = False
            current = None
            waiting_list = False
        if not in_jobs:
            continue
        mjob = _JOB_KEY.match(line)
        if mjob:
            current = mjob.group(1)
            nodes.add(current)
            waiting_list = False
            continue
        if current is None:
            continue
        minl = _NEEDS_INLINE.match(line)
        if minl and minl.group(1) is not None and minl.group(1).strip():
            for dep in _parse_needs_value(minl.group(1)):
                nodes.add(dep)
                edges.add((dep, current))
            waiting_list = False
            continue
        if _NEEDS_KEY.match(line):
            waiting_list = True
            continue
        if waiting_list:
            item = _LIST_ITEM.match(line)
            if item:
                dep = item.group(1).strip().strip("'\"")
                nodes.add(dep)
                edges.add((dep, current))
                continue
            waiting_list = False
    return nodes, edges


def topo_kahn(nodes: set[str], edges: set[tuple[str, str]]) -> list[str] | None:
    """Kahn (BFS indegree) linearisation. None if a cycle exists."""
    succ: dict[str, list[str]] = defaultdict(list)
    indeg = {n: 0 for n in nodes}
    for u, v in edges:
        indeg.setdefault(u, 0)
        indeg.setdefault(v, 0)
        succ[u].append(v)
        indeg[v] += 1
        if u not in indeg:
            indeg[u] = 0
    ready = deque(sorted(n for n, d in indeg.items() if d == 0))
    order: list[str] = []
    while ready:
        n = ready.popleft()
        order.append(n)
        for m in sorted(succ[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    if len(order) != len(indeg):
        return None
    return order


def topo_dfs(nodes: set[str], edges: set[tuple[str, str]]) -> list[str] | None:
    """DFS finishing-time linearisation (reverse postorder). None on cycle."""
    succ: dict[str, list[str]] = defaultdict(list)
    for u, v in edges:
        succ[u].append(v)
    UNSEEN, OPEN, DONE = 0, 1, 2
    state = {n: UNSEEN for n in nodes}
    for u, v in edges:
        state.setdefault(u, UNSEEN)
        state.setdefault(v, UNSEEN)
    order_rev: list[str] = []
    cycle = False

    def visit(n: str) -> None:
        nonlocal cycle
        if state[n] == DONE or cycle:
            return
        if state[n] == OPEN:
            cycle = True
            return
        state[n] = OPEN
        for m in sorted(succ[n]):
            visit(m)
        state[n] = DONE
        order_rev.append(n)

    for n in sorted(state):
        if state[n] == UNSEEN:
            visit(n)
    if cycle:
        return None
    return list(reversed(order_rev))


def is_valid_topo(order: list[str], edges: set[tuple[str, str]]) -> bool:
    idx = {n: i for i, n in enumerate(order)}
    for u, v in edges:
        if u not in idx or v not in idx:
            return False
        if idx[u] >= idx[v]:
            return False
    return True
