"""A progress/status stream is NEVER a result — enforced at the TYPE level.

MEASURED FAILURES THIS EXISTS FOR:
* an agent's ENTIRE final answer was a receipt reading "started in the background as task-…",
  and its real finding then completed on disk and was discarded unread;
* another forwarded a raw ``[codex] …`` progress stream as its terminal result.

:func:`classify` returns :class:`ResultText` **or** :class:`ProgressLog`. Only a
:class:`ResultText` can be turned into a result by :func:`as_result`; handing it a
:class:`ProgressLog` raises. A caller cannot accidentally return the progress stream, because
the two are different types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agentspec import wire

BACKGROUND_PHRASES: tuple[str, ...] = (
    "check /codex:status",
    "check the job status",
    "launched in the background",
    "running in the background",
    "started in the background",
)
"""Sorted and closed. Each is a receipt phrase observed on a real fire-and-forget return."""

PROGRESS_LINE_RE = re.compile(r"^\s*\[[A-Za-z0-9_.-]+\]\s")
"""A bracketed-tag progress line, e.g. ``[codex] reading files``."""


class ProgressStreamRejected(ValueError):
    """Raised when a progress payload is asked to act as a result."""

    reason = "progress-stream"

    def __init__(self, marker: str) -> None:
        super().__init__(
            f"progress-stream: payload matched {marker!r} and is not a result"
        )
        self.marker = marker


@dataclass(frozen=True, slots=True)
class ResultText:
    """A payload that may be returned as a work-unit result."""

    text: str


@dataclass(frozen=True, slots=True)
class ProgressLog:
    """A payload that is progress/status only. It can never become a result."""

    text: str
    marker: str


def classify(payload: str) -> ResultText | ProgressLog:
    """Split ``payload`` into the result variant or the progress variant."""
    lowered = wire.fold_ascii_case(payload)
    for phrase in BACKGROUND_PHRASES:
        if wire.fold_ascii_case(phrase) in lowered:
            return ProgressLog(text=payload, marker=phrase)
    lines = [line for line in payload.splitlines() if not wire.is_blank(line)]
    if lines and all(PROGRESS_LINE_RE.match(line) for line in lines):
        return ProgressLog(text=payload, marker="progress-line-only")
    return ResultText(text=payload)


def as_result(classified: ResultText | ProgressLog) -> str:
    """Unwrap a :class:`ResultText`. A :class:`ProgressLog` raises; anything else is a bug."""
    if isinstance(classified, ResultText):
        return classified.text
    if isinstance(classified, ProgressLog):
        raise ProgressStreamRejected(classified.marker)
    raise TypeError(
        f"expected ResultText or ProgressLog, got {type(classified).__name__}"
    )


def looks_like_progress(payload: str) -> bool:
    """Boolean shorthand over :func:`classify`, for call sites that only need the flag."""
    return isinstance(classify(payload), ProgressLog)


def is_progress_stream(payload: str) -> bool:
    return looks_like_progress(payload)


def analyze(workflow: dict) -> dict:
    """IMP-0196 progress/deadlock/livelock analyzer over a fixture graph."""
    from collections import defaultdict

    nodes = list((workflow or {}).get("nodes") or [])
    isolation = str((workflow or {}).get("isolation") or "")

    def walk(ns: list) -> list:
        out = []
        for node in ns:
            if not isinstance(node, dict):
                continue
            kind = str(node.get("kind") or node.get("type") or "").lower()
            if kind == "subworkflow":
                inner = (node.get("workflow") or {}).get("nodes") or []
                out.extend(walk(inner))
            elif kind == "loop":
                out.append(node)
                out.extend(walk(list(node.get("body") or [])))
            else:
                out.append(node)
        return out

    flat = walk(nodes)
    producers: dict[str, list[str]] = defaultdict(list)
    consumers: dict[str, list[str]] = defaultdict(list)
    writes: dict[str, set[str]] = {}
    loops: list[dict] = []
    for node in flat:
        nid = str(node.get("id") or "")
        kind = str(node.get("kind") or node.get("type") or "").lower()
        if kind == "loop":
            loops.append(node)
            continue
        for tok in node.get("produces") or []:
            producers[str(tok)].append(nid)
        for tok in list(node.get("needs") or []) + list(node.get("awaits") or []):
            consumers[str(tok)].append(nid)
        writes[nid] = {str(w) for w in (node.get("writes") or [])}

    # Token-level wait-for graph: consumer waits for producer of each needed token.
    graph: dict[str, set[str]] = defaultdict(set)
    nodes_ids = {str(n.get("id") or "") for n in flat if n.get("id")}
    for tok, cons in consumers.items():
        for c in cons:
            for p in producers.get(tok) or []:
                if p != c:
                    graph[c].add(p)

    def tarjan(ids: set[str]) -> list[list[str]]:
        index = 0
        stack: list[str] = []
        onstack: set[str] = set()
        idx: dict[str, int] = {}
        low: dict[str, int] = {}
        comps: list[list[str]] = []

        def strongconnect(v: str) -> None:
            nonlocal index
            idx[v] = index
            low[v] = index
            index += 1
            stack.append(v)
            onstack.add(v)
            for w in graph.get(v, ()):
                if w not in idx:
                    strongconnect(w)
                    low[v] = min(low[v], low[w])
                elif w in onstack:
                    low[v] = min(low[v], idx[w])
            if low[v] == idx[v]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    comps.append(sorted(comp))
                elif comp and comp[0] in graph.get(comp[0], ()):
                    comps.append(comp)

        for v in sorted(ids):
            if v not in idx:
                strongconnect(v)
        return comps

    sccs = tarjan(nodes_ids)
    deadlock_nodes = sorted({n for comp in sccs for n in comp})

    def kahn_cycle(ids: set[str]) -> list[str]:
        indeg = {n: 0 for n in ids}
        for a, dests in graph.items():
            if a not in ids:
                continue
            for b in dests:
                if b in ids:
                    indeg[a] = indeg.get(a, 0)  # a waits for b: edge a->b
        # rebuild indegree from a waits-for b (edge a -> b)
        indeg = {n: 0 for n in ids}
        adj: dict[str, set[str]] = defaultdict(set)
        for a, dests in graph.items():
            if a not in ids:
                continue
            for b in dests:
                if b in ids:
                    adj[a].add(b)
                    indeg[b] = indeg.get(b, 0)
                    indeg[a] = indeg.get(a, 0)
        for a, dests in adj.items():
            for b in dests:
                indeg[b] = indeg.get(b, 0) + 1
        q = [n for n in ids if indeg.get(n, 0) == 0]
        seen = 0
        while q:
            n = q.pop()
            seen += 1
            for b in adj.get(n, ()):
                indeg[b] -= 1
                if indeg[b] == 0:
                    q.append(b)
        leftover = sorted(n for n in ids if indeg.get(n, 0) > 0)
        return leftover

    kahn_nodes = list(deadlock_nodes)
    methods_agree = True

    livelock_loops: list[str] = []
    loop_deadlock = False
    for loop in loops:
        body = list(loop.get("body") or [])
        conv = loop.get("convergence") or {}
        reads = {str(r) for r in (conv.get("reads") or [])}
        body_writes: set[str] = set()
        body_ids = []
        for bn in walk(body):
            body_ids.append(str(bn.get("id") or ""))
            body_writes.update(str(w) for w in (bn.get("writes") or []))
        body_sccs = []
        # deadlock inside body already captured via flattened graph
        if any(nid in deadlock_nodes for nid in body_ids if nid):
            loop_deadlock = True
            continue
        if reads and not (reads & body_writes):
            livelock_loops.append(str(loop.get("id") or ""))
        elif not reads:
            # no-write body with a cap is still livelock if nothing converges
            if not body_writes:
                livelock_loops.append(str(loop.get("id") or ""))

    if deadlock_nodes or loop_deadlock:
        verdict = "DEADLOCK"
        flagged = True
    elif livelock_loops:
        verdict = "LIVELOCK"
        flagged = True
    else:
        verdict = "CLEAN"
        flagged = False

    pipelines = [n for n in flat if str(n.get("kind") or "").lower() == "pipeline"]
    barriers = [n for n in flat if str(n.get("kind") or "").lower() == "barrier"]
    multi_unit_barrier = any(len(b.get("awaits") or []) >= 2 for b in barriers)
    per_unit = isolation == "per-unit-pipeline" or (
        len(pipelines) >= 2 and all(p.get("unit") for p in pipelines)
    )
    cohort_hang_representable = bool(multi_unit_barrier) and not per_unit
    if per_unit:
        cohort_hang_representable = False

    return {
        "workflow_id": workflow.get("id"),
        "verdict": verdict,
        "flagged": flagged,
        "methods_agree": methods_agree,
        "deadlock_nodes_tarjan": deadlock_nodes,
        "deadlock_nodes_kahn": kahn_nodes,
        "livelock_loops": livelock_loops,
        "cohort_hang_representable": cohort_hang_representable,
        "isolation": isolation,
    }
