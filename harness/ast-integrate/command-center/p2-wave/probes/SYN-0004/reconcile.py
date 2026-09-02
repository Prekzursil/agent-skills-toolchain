"""Bottom-up max-not-mean severity reconciliation over a typed causal graph."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from severity import (
    RANK,
    UnknownSeverityError,
    max_token,
    nearest_mean_token,
    parse_severity,
)

CAUSE_TYPES = frozenset({"CAUSE"})
CLAIM_TYPES = frozenset({"SYMPTOM", "CLAIM", "FINDING"})


class GraphError(ValueError):
    pass


class GraphCycleError(GraphError):
    pass


def _as_id(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _node_severity_raw(node: dict) -> object:
    for key in ("severity", "recorded_severity", "severity_token"):
        if key in node and node[key] is not None:
            return node[key]
    return None


def _flatten_nested(node: dict, acc: list[dict], edges: list[tuple[str, str]]) -> None:
    nid = _as_id(node.get("id"))
    if not nid:
        raise GraphError(f"node missing id: {node!r}"[:200])
    acc.append(node)
    kids = node.get("children") or node.get("child_ids") or []
    if not isinstance(kids, list):
        return
    for kid in kids:
        if isinstance(kid, str):
            cid = _as_id(kid)
            if cid:
                edges.append((nid, cid))
        elif isinstance(kid, dict):
            cid = _as_id(kid.get("id"))
            if cid:
                edges.append((nid, cid))
            _flatten_nested(kid, acc, edges)


def normalize(doc: dict) -> tuple[dict[str, dict], dict[str, list[str]]]:
    if not isinstance(doc, dict):
        raise GraphError(f"graph is not an object: {type(doc).__name__}")
    raw_nodes: list[Any] = []
    extra_edges: list[tuple[str, str]] = []
    graph = doc.get("graph") if isinstance(doc.get("graph"), dict) else {}
    if isinstance(doc.get("nodes"), list):
        raw_nodes.extend(doc["nodes"])
    elif isinstance(graph.get("nodes"), list):
        raw_nodes.extend(graph["nodes"])
    elif isinstance(doc.get("causes"), list):
        for cause in doc["causes"]:
            if isinstance(cause, dict):
                _flatten_nested(cause, raw_nodes, extra_edges)
    elif isinstance(doc.get("roots"), list):
        for root in doc["roots"]:
            if isinstance(root, dict):
                _flatten_nested(root, raw_nodes, extra_edges)
    else:
        raise GraphError("graph has no nodes, causes, or roots")

    nodes: dict[str, dict] = {}
    children: dict[str, list[str]] = defaultdict(list)
    for item in raw_nodes:
        if not isinstance(item, dict):
            raise GraphError("node entry is not an object")
        nid = _as_id(item.get("id"))
        if not nid:
            raise GraphError("node missing id")
        if nid in nodes:
            raise GraphError(f"duplicate node id {nid}")
        ntype = str(item.get("type") or item.get("node_type") or "CAUSE").upper()
        claim_id = _as_id(item.get("claim_id"))
        claim_ids = []
        raw_ids = item.get("claim_ids") or []
        if isinstance(raw_ids, list):
            claim_ids = [c for c in (_as_id(x) for x in raw_ids) if c]
        if claim_id and claim_id not in claim_ids:
            claim_ids.insert(0, claim_id)
        nodes[nid] = {
            "id": nid,
            "type": ntype,
            "severity": parse_severity(_node_severity_raw(item)),
            "claim_ids": claim_ids,
        }
        kids = item.get("children") or item.get("child_ids") or []
        if isinstance(kids, list):
            for kid in kids:
                cid = _as_id(kid) if not isinstance(kid, dict) else _as_id(kid.get("id"))
                if cid and cid not in children[nid]:
                    children[nid].append(cid)

    edge_lists = []
    if isinstance(doc.get("edges"), list):
        edge_lists.append(doc["edges"])
    if isinstance(graph.get("edges"), list):
        edge_lists.append(graph["edges"])
    for batch in edge_lists:
        for edge in batch:
            if not isinstance(edge, dict):
                continue
            parent = _as_id(
                edge.get("parent") or edge.get("from") or edge.get("source")
            )
            child = _as_id(edge.get("child") or edge.get("to") or edge.get("target"))
            if parent and child and child not in children[parent]:
                extra_edges.append((parent, child))
    for parent, child in extra_edges:
        if child not in children[parent]:
            children[parent].append(child)

    for parent, kids in children.items():
        if parent not in nodes:
            raise GraphError(f"edge parent {parent} does not exist")
        for child in kids:
            if child not in nodes:
                raise GraphError(f"edge endpoint {child} does not exist")
    for nid in nodes:
        children.setdefault(nid, [])
    return nodes, dict(children)


def _parents_of(children: dict[str, list[str]]) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = defaultdict(list)
    for parent, kids in children.items():
        for child in kids:
            if parent not in parents[child]:
                parents[child].append(parent)
    return parents


def _subtree_max(
    nid: str,
    nodes: dict[str, dict],
    children: dict[str, list[str]],
    visiting: set[str],
    cache: dict[str, str | None],
) -> str | None:
    if nid in cache:
        return cache[nid]
    if nid in visiting:
        raise GraphCycleError(f"cycle at {nid}")
    visiting.add(nid)
    best: str | None = None
    for cid in children.get(nid) or []:
        child_rec = nodes[cid]["severity"]
        best = child_rec if best is None else max_token((best, child_rec))
        desc = _subtree_max(cid, nodes, children, visiting, cache)
        if desc is not None:
            best = desc if best is None else max_token((best, desc))
    visiting.remove(nid)
    cache[nid] = best
    return best


def _witnesses(
    nid: str,
    target: str,
    nodes: dict[str, dict],
    children: dict[str, list[str]],
) -> list[str]:
    found: list[str] = []

    def walk(cur: str) -> None:
        for cid in children.get(cur) or []:
            child = nodes[cid]
            ids = list(child["claim_ids"])
            if child["severity"] == target:
                found.append(ids[0] if ids else cid)
            walk(cid)

    walk(nid)
    # Stable unique, prefer claim ids that actually match the max token.
    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def classify_row(
    recorded: str,
    max_child: str | None,
    direct_child_tokens: list[str],
) -> tuple[str, int]:
    if max_child is None:
        return "ALIGNED", 0
    rec = parse_severity(recorded)
    mx = parse_severity(max_child)
    delta = max(0, RANK[mx] - RANK[rec])
    if delta == 0:
        return "ALIGNED", 0
    mean = nearest_mean_token(direct_child_tokens) if direct_child_tokens else None
    if mean is not None and rec == mean and rec != mx:
        return "DILUTION", delta
    return "INVERSION", delta


def _nearest_cause(
    nid: str,
    nodes: dict[str, dict],
    parents: dict[str, list[str]],
) -> str | None:
    seen: set[str] = set()
    stack = list(parents.get(nid) or [])
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if nodes[cur]["type"] in CAUSE_TYPES:
            return cur
        stack.extend(parents.get(cur) or [])
    return None


def p0_p1_stats(
    nodes: dict[str, dict],
    children: dict[str, list[str]],
    rows_by_id: dict[str, dict],
) -> dict:
    parents = _parents_of(children)
    total = 0
    attached = 0
    survived = 0
    diluted = 0
    unattached = 0
    for nid, node in nodes.items():
        sev = node["severity"]
        if sev not in ("P0", "P1"):
            continue
        is_claim = bool(node["claim_ids"]) or node["type"] in CLAIM_TYPES
        if node["type"] in CAUSE_TYPES and not is_claim:
            continue
        if not is_claim and node["type"] in CAUSE_TYPES:
            continue
        if not is_claim and node["type"] not in CLAIM_TYPES:
            continue
        total += 1
        cause_id = _nearest_cause(nid, nodes, parents)
        if cause_id is None:
            unattached += 1
            continue
        attached += 1
        recorded = rows_by_id[cause_id]["recorded_severity"]
        if recorded == sev:
            survived += 1
        else:
            diluted += 1
    return {
        "total": total,
        "attached_to_cause": attached,
        "survived_unchanged": survived,
        "diluted_or_inverted": diluted,
        "unattached": unattached,
    }


def reconcile(doc: dict) -> dict:
    nodes, children = normalize(doc)
    cache: dict[str, str | None] = {}
    visiting: set[str] = set()
    rows: list[dict] = []
    for nid, node in nodes.items():
        if node["type"] not in CAUSE_TYPES:
            continue
        max_child = _subtree_max(nid, nodes, children, visiting, cache)
        direct = [nodes[c]["severity"] for c in children.get(nid) or []]
        verdict, delta = classify_row(node["severity"], max_child, direct)
        named = _witnesses(nid, max_child, nodes, children) if delta else []
        rows.append(
            {
                "cause_id": nid,
                "recorded_severity": node["severity"],
                "computed_max_child_severity": max_child,
                "delta": delta,
                "verdict": verdict,
                "child_claim_id": named[0] if named else None,
                "child_claim_ids": named,
                "direct_child_count": len(children.get(nid) or []),
            }
        )
    rows.sort(key=lambda r: r["cause_id"])
    unexplained = [
        r
        for r in rows
        if r["delta"] != 0 and r["verdict"] not in ("INVERSION", "DILUTION")
    ]
    findings = [r for r in rows if r["delta"] != 0]
    rows_by_id = {r["cause_id"]: r for r in rows}
    return {
        "rows": rows,
        "findings": findings,
        "unexplained": unexplained,
        "unexplained_count": len(unexplained),
        "p0_p1": p0_p1_stats(nodes, children, rows_by_id),
        "cause_count": len(rows),
        "node_count": len(nodes),
    }


# Re-export for probes that catch the author exception type.
UnknownSeverityError = UnknownSeverityError
