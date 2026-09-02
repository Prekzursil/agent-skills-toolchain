"""Static deadlock / livelock analysis over Loop x Barrier x Subworkflow graphs.

Two independent cycle derivations must agree: Tarjan SCC and Kahn remainder
(forward peel intersected with reverse peel, so downstream-blocked nodes are
not reported as cyclic). A Loop whose body never writes a convergence-read
key is LIVELOCK, a distinct verdict; a wait-for cycle inside the body is
DEADLOCK and takes precedence.

Cohort-hang (one hung unit blocking a multi-unit barrier) is representable
when a barrier awaits two or more tokens produced by units. It is
unrepresentable when every awaited token is produced by a timed Pipeline.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

OPERATIONAL = frozenset({"unit", "barrier", "pipeline"})


def _qid(prefix: str, ident: str) -> str:
    return f"{prefix}/{ident}" if prefix else ident


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(x) for x in value)


def _flatten(
    nodes: list[Any], prefix: str = ""
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    flats: list[dict[str, Any]] = []
    loops: list[dict[str, Any]] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "")
        nid = _qid(prefix, str(raw.get("id") or ""))
        if kind == "subworkflow":
            ns = str(raw.get("id_namespace") or raw.get("id") or "")
            inner_wf = raw.get("workflow") or {}
            inner_nodes = inner_wf.get("nodes") if isinstance(inner_wf, dict) else []
            if not isinstance(inner_nodes, list):
                inner_nodes = []
            f, l = _flatten(inner_nodes, _qid(prefix, ns))
            flats.extend(f)
            loops.extend(l)
            continue
        if kind == "loop":
            body = raw.get("body") or []
            if not isinstance(body, list):
                body = []
            f, l = _flatten(body, _qid(prefix, str(raw.get("id") or "")))
            flats.extend(f)
            loops.extend(l)
            conv = raw.get("convergence") if isinstance(raw.get("convergence"), dict) else {}
            writes: set[str] = set()
            for fn in f:
                writes.update(fn["writes"])
            loops.append(
                {
                    "id": nid,
                    "reads": _as_str_tuple(conv.get("reads")),
                    "body_ids": tuple(fn["id"] for fn in f),
                    "writes": tuple(sorted(writes)),
                }
            )
            continue
        if kind not in OPERATIONAL:
            continue
        consumed = list(_as_str_tuple(raw.get("needs")))
        if kind == "barrier":
            consumed.extend(_as_str_tuple(raw.get("awaits")))
        produced = list(_as_str_tuple(raw.get("produces")))
        unit_ref = str(raw.get("unit") or "")
        flats.append(
            {
                "id": nid,
                "kind": kind,
                "needs": tuple(_qid(prefix, t) for t in consumed),
                "produces": tuple(_qid(prefix, t) for t in produced),
                "writes": _as_str_tuple(raw.get("writes")),
                "timeout_s": int(raw.get("timeout_s") or 0),
                "unit_ref": _qid(prefix, unit_ref) if unit_ref else "",
            }
        )
    return flats, loops


def _tarjan_cyclic(nodes: list[str], succs: dict[str, list[str]]) -> list[str]:
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    onstack: set[str] = set()
    stack: list[str] = []
    cyclic: list[str] = []
    counter = 0

    def strongconnect(v: str) -> None:
        nonlocal counter
        index[v] = counter
        low[v] = counter
        counter += 1
        stack.append(v)
        onstack.add(v)
        for w in succs.get(v, ()):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                comp.append(w)
                if w == v:
                    break
            nontrivial = len(comp) > 1 or v in succs.get(v, ())
            if nontrivial:
                cyclic.extend(comp)

    for node in nodes:
        if node not in index:
            strongconnect(node)
    return sorted(cyclic)


def _kahn_unpeeled(nodes: list[str], succs: dict[str, list[str]]) -> set[str]:
    indeg = {n: 0 for n in nodes}
    for u in nodes:
        for v in succs.get(u, ()):
            if v in indeg:
                indeg[v] += 1
    queue: deque[str] = deque(n for n in nodes if indeg[n] == 0)
    peeled: set[str] = set()
    while queue:
        n = queue.popleft()
        peeled.add(n)
        for v in succs.get(n, ()):
            if v not in indeg or v in peeled:
                continue
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    return {n for n in nodes if n not in peeled}


def _reverse(nodes: list[str], succs: dict[str, list[str]]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = {n: [] for n in nodes}
    for u in nodes:
        for v in succs.get(u, ()):
            if v in rev and u not in rev[v]:
                rev[v].append(u)
    return rev


def _wait_for_graph(flats: list[dict[str, Any]]) -> tuple[list[str], dict[str, list[str]]]:
    ids = [fn["id"] for fn in flats if fn["id"]]
    idset = set(ids)
    producers: dict[str, list[str]] = defaultdict(list)
    for fn in flats:
        for tok in fn["produces"]:
            producers[tok].append(fn["id"])
    succs: dict[str, list[str]] = {n: [] for n in ids}
    for fn in flats:
        waiter = fn["id"]
        deps: list[str] = []
        for tok in fn["needs"]:
            deps.extend(producers.get(tok, ()))
        uref = fn["unit_ref"]
        if uref and uref in idset:
            deps.append(uref)
        for pred in deps:
            if pred not in succs:
                continue
            if waiter not in succs[pred]:
                succs[pred].append(waiter)
    return ids, succs


def _cohort_hang_representable(flats: list[dict[str, Any]]) -> bool:
    producers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fn in flats:
        for tok in fn["produces"]:
            producers[tok].append(fn)
    for fn in flats:
        if fn["kind"] != "barrier" or len(fn["needs"]) < 2:
            continue
        prod: list[dict[str, Any]] = []
        for tok in fn["needs"]:
            prod.extend(producers.get(tok, ()))
        if not prod:
            continue
        if all(p["kind"] == "pipeline" and p["timeout_s"] > 0 for p in prod):
            continue
        unit_ids = {p["id"] for p in prod if p["kind"] == "unit"}
        if len(unit_ids) >= 1:
            return True
    return False


def analyze(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return a verdict report for one workflow dict (fixture dialect)."""
    nodes = workflow.get("nodes") if isinstance(workflow, dict) else []
    if not isinstance(nodes, list):
        nodes = []
    flats, loops = _flatten(nodes)
    ids, succs = _wait_for_graph(flats)
    tarjan_nodes = _tarjan_cyclic(ids, succs)
    kahn_fwd = _kahn_unpeeled(ids, succs)
    kahn_rev = _kahn_unpeeled(ids, _reverse(ids, succs))
    kahn_cycle = sorted(kahn_fwd & kahn_rev)
    methods_agree = tarjan_nodes == kahn_cycle
    deadlock_set = set(tarjan_nodes)

    livelock_loops: list[str] = []
    for loop in loops:
        reads = set(loop["reads"])
        writes = set(loop["writes"])
        body_deadlocked = bool(deadlock_set.intersection(loop["body_ids"]))
        if reads and reads.isdisjoint(writes) and not body_deadlocked:
            livelock_loops.append(loop["id"])

    if tarjan_nodes:
        verdict = "DEADLOCK"
    elif livelock_loops:
        verdict = "LIVELOCK"
    else:
        verdict = "CLEAN"

    return {
        "workflow_id": str(workflow.get("id") or ""),
        "verdict": verdict,
        "flagged": verdict != "CLEAN",
        "methods_agree": methods_agree,
        "cycle_methods": "tarjan_scc AND kahn_remainder",
        "deadlock_nodes_tarjan": tarjan_nodes,
        "deadlock_nodes_kahn": kahn_cycle,
        "livelock_loops": livelock_loops,
        "cohort_hang_representable": _cohort_hang_representable(flats),
    }
