"""Structural checks for a typed CAUSE|MECHANISM|SYMPTOM DAG."""
from __future__ import annotations

from collections import defaultdict, deque
from statistics import median
from typing import Any


NODE_TYPES = ("CAUSE", "MECHANISM", "SYMPTOM")
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def index_nodes(doc: dict) -> dict[str, dict]:
    nodes = {}
    for n in doc.get("nodes") or []:
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            raise ValueError("node-missing-id")
        if nid in nodes:
            raise ValueError(f"duplicate-node:{nid}")
        nodes[nid] = n
    return nodes


def edge_list(doc: dict) -> list[dict]:
    return [e for e in (doc.get("edges") or []) if isinstance(e, dict)]


def successors(doc: dict) -> dict[str, list[str]]:
    succ: dict[str, list[str]] = defaultdict(list)
    for e in edge_list(doc):
        succ[str(e.get("from"))].append(str(e.get("to")))
    return succ


def has_cycle(doc: dict) -> bool:
    nodes = index_nodes(doc)
    succ = successors(doc)
    indeg = {nid: 0 for nid in nodes}
    for e in edge_list(doc):
        dst = str(e.get("to"))
        if dst not in indeg:
            raise ValueError(f"dangling-edge-to:{dst}")
        src = str(e.get("from"))
        if src not in nodes:
            raise ValueError(f"dangling-edge-from:{src}")
        indeg[dst] += 1
    q = deque([n for n, d in indeg.items() if d == 0])
    seen = 0
    while q:
        cur = q.popleft()
        seen += 1
        for nxt in succ.get(cur, []):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return seen != len(nodes)


def max_depth(doc: dict) -> int:
    """Longest path length in edges from any in-degree-0 node."""
    nodes = index_nodes(doc)
    succ = successors(doc)
    indeg = {nid: 0 for nid in nodes}
    for e in edge_list(doc):
        indeg[str(e["to"])] += 1
    roots = [n for n, d in indeg.items() if d == 0]
    best = 0
    for r in roots:
        dist = {r: 0}
        q = deque([r])
        while q:
            cur = q.popleft()
            for nxt in succ.get(cur, []):
                nd = dist[cur] + 1
                if nd > dist.get(nxt, -1):
                    dist[nxt] = nd
                    q.append(nxt)
                    if nd > best:
                        best = nd
    return best


def reachable(succ: dict[str, list[str]], start: str) -> set[str]:
    out: set[str] = set()
    q = deque([start])
    while q:
        cur = q.popleft()
        for nxt in succ.get(cur, []):
            if nxt not in out:
                out.add(nxt)
                q.append(nxt)
    return out


def cause_typed_edges_to_symptoms(doc: dict) -> tuple[bool, str]:
    nodes = index_nodes(doc)
    succ = successors(doc)
    by_pair = {(e["from"], e["to"]): e for e in edge_list(doc)}
    causes = [n for n in nodes.values() if n.get("type") == "CAUSE"]
    if not causes:
        return False, "no-cause-nodes"
    for cause in causes:
        cid = cause["id"]
        reached = reachable(succ, cid)
        symptoms = [
            nid for nid in reached if nodes.get(nid, {}).get("type") == "SYMPTOM"
        ]
        if not symptoms:
            return False, f"cause-without-symptom:{cid}"
        for sid in symptoms:
            if not _path_with_named_mechanism(succ, by_pair, cid, sid):
                return False, f"unnamed-mechanism-path:{cid}->{sid}"
    for e in edge_list(doc):
        mech = str(e.get("mechanism") or "").strip()
        if len(mech) < 8:
            return False, f"edge-mechanism-too-short:{e.get('from')}->{e.get('to')}"
        dst = nodes.get(str(e.get("to")))
        if dst and dst.get("type") == "SYMPTOM" and not mech:
            return False, f"symptom-edge-missing-mechanism:{e.get('from')}"
    return True, "ok"


def _path_with_named_mechanism(
    succ: dict[str, list[str]],
    by_pair: dict[tuple[str, str], dict],
    start: str,
    goal: str,
) -> bool:
    q = deque([(start, True)])
    seen = {(start, True)}
    while q:
        cur, ok = q.popleft()
        if cur == goal and ok and cur != start:
            return True
        for nxt in succ.get(cur, []):
            e = by_pair.get((cur, nxt), {})
            named = len(str(e.get("mechanism") or "").strip()) >= 8
            flag = ok and named
            key = (nxt, flag)
            if key not in seen:
                seen.add(key)
                q.append((nxt, flag))
    return False


def median_branching(doc: dict) -> float:
    succ = successors(doc)
    nodes = index_nodes(doc)
    degrees = [len(succ.get(nid, [])) for nid in nodes]
    live = [d for d in degrees if d > 0]
    if not live:
        return 0.0
    return float(median(live))


def counts(doc: dict) -> dict[str, int]:
    c = {t: 0 for t in NODE_TYPES}
    for n in doc.get("nodes") or []:
        t = n.get("type")
        if t in c:
            c[t] += 1
    return c


def metrics(doc: dict) -> dict[str, Any]:
    c = counts(doc)
    causes = c["CAUSE"] or 1
    return {
        "node_count_by_type": c,
        "node_count": sum(c.values()),
        "edge_count": len(edge_list(doc)),
        "max_depth": max_depth(doc),
        "median_branching_factor": median_branching(doc),
        "findings_per_root_cause": round(c["SYMPTOM"] / causes, 4),
        "root_cause_count": c["CAUSE"],
        "acyclic": not has_cycle(doc),
        "acyclic": not has_cycle(doc),
        "root_cause_count": c["CAUSE"],
        "root_cause_count": c["CAUSE"],
        "node_count_by_type": c,
        "node_count_by_type": c,
    }


def structural_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-object"]
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        errs.append(f"self-declared:{st}")
    try:
        nodes = index_nodes(doc)
    except ValueError as exc:
        return [str(exc)]
    for e in edge_list(doc):
        if e.get("from") not in nodes:
            errs.append(f"dangling-from:{e.get('from')}")
        if e.get("to") not in nodes:
            errs.append(f"dangling-to:{e.get('to')}")
        if not str(e.get("mechanism") or "").strip():
            errs.append(f"edge-missing-mechanism:{e.get('from')}->{e.get('to')}")
    try:
        if has_cycle(doc):
            errs.append("cycle-in-causal-graph")
    except ValueError as exc:
        errs.append(str(exc))
    depth = max_depth(doc)
    if depth < 2:
        errs.append(f"flat-list-masquerading-as-hierarchy:max_depth={depth}")
    ok, why = cause_typed_edges_to_symptoms(doc)
    if not ok:
        errs.append(why)
    for n in nodes.values():
        if n.get("type") != "CAUSE":
            continue
        anchors = n.get("evidence_anchors") or []
        files = {
            str(a.get("path"))
            for a in anchors
            if isinstance(a, dict) and a.get("path")
        }
        single = bool(n.get("single_source")) or str(n.get("label") or "") == "SINGLE-SOURCE"
        if len(anchors) < 2 and not single:
            errs.append(f"unanchored-cause-node:{n.get('id')}:anchors={len(anchors)}")
        elif len(anchors) >= 2 and len(files) < 2 and not single:
            errs.append(f"unanchored-cause-node:{n.get('id')}:same-file")
        if single and len(anchors) != 1:
            errs.append(f"single-source-mislabelled:{n.get('id')}")
    return errs


# Aliases used by emit/probes (kept so a rename cannot split the contract).
structural_errors = structural_errors
NOT_DELIVERING = NOT_DELIVERING
cause_typed_edges_to_symptoms = cause_typed_edges_to_symptoms
cause_typed_edges_to_symptoms = cause_typed_edges_to_symptoms
