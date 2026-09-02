"""Pure counterfactual intervention ranking for SYN-0007.

Score for candidate I:
  score_micro = (subtree_size * severity_weight * 1_000_000) // cost_seconds
where subtree_size is the number of distinct descendant claim ids,
severity is max-not-mean over the prevented set, and cost is DERIVED
(timeout seconds) or ESTIMATE (band midpoint). Unknown severity tokens
fail closed. Asserted cost without a band is rejected, not defaulted.
Phase anachronism (intervention later than a finding it claims to prevent)
is rejected, not ranked.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

SEVERITY_WEIGHT = {"P0": 8, "P1": 4, "P2": 2, "P3": 1}
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
ESTIMATE_BAND_SECONDS = {"XS": 900, "S": 1800, "M": 3600, "L": 7200, "XL": 14400}
PHASE_ORDER = [
    "0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6",
    "7", "7A", "8", "9", "10", "11", "12", "13", "14", "15", "16",
]
PHASE_INDEX = {p: i for i, p in enumerate(PHASE_ORDER)}
CANDIDATE_TYPES = frozenset({"CAUSE", "MECHANISM"})


class RankError(ValueError):
    def __init__(self, classification: str, detail: str = "") -> None:
        super().__init__(f"{classification}: {detail}".strip())
        self.classification = classification
        self.detail = detail


def phase_index(phase: str) -> int:
    key = str(phase or "").strip()
    if key not in PHASE_INDEX:
        raise RankError("unknown-phase", key or "<empty>")
    return PHASE_INDEX[key]


def severity_weight(token: str) -> int:
    tok = str(token or "").strip().upper()
    if tok not in SEVERITY_WEIGHT:
        raise RankError("unknown-severity-token", tok or "<empty>")
    return SEVERITY_WEIGHT[tok]


def max_severity(tokens: list[str]) -> str:
    if not tokens:
        raise RankError("unknown-severity-token", "empty-set")
    best = None
    best_rank = 99
    for tok in tokens:
        t = str(tok or "").strip().upper()
        if t not in SEVERITY_RANK:
            raise RankError("unknown-severity-token", t or "<empty>")
        if SEVERITY_RANK[t] < best_rank:
            best_rank = SEVERITY_RANK[t]
            best = t
    assert best is not None
    return best


def children_map(edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for e in edges:
        parent, child = str(e.get("parent") or ""), str(e.get("child") or "")
        if not parent or not child or parent == child:
            continue
        pair = (parent, child)
        if pair in seen:
            continue
        seen.add(pair)
        out[parent].append(child)
    return out


def assert_acyclic(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    kids = children_map(edges)
    ids = [str(n["id"]) for n in nodes]
    white, grey, black = 0, 1, 2
    color = {i: white for i in ids}

    def dfs(u: str) -> None:
        color[u] = grey
        for v in kids.get(u, []):
            if v not in color:
                continue
            if color[v] == grey:
                raise RankError("unstable-ranking", f"cycle {u}->{v}")
            if color[v] == white:
                dfs(v)
        color[u] = black

    for i in ids:
        if color[i] == white:
            dfs(i)


def descendants(node_id: str, kids: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    seen = {node_id}
    q = deque(kids.get(node_id, []))
    while q:
        u = q.popleft()
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        q.extend(kids.get(u, []))
    return out


def max_depth(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> int:
    kids = children_map(edges)
    ids = {str(n["id"]) for n in nodes}
    incoming = {i: 0 for i in ids}
    for parent, children in kids.items():
        if parent not in incoming:
            continue
        for child in children:
            if child in incoming:
                incoming[child] += 1
    roots = [i for i, n in incoming.items() if n == 0]
    best = 0
    for root in roots:
        stack = [(root, 0)]
        seen: set[str] = set()
        while stack:
            u, depth = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            if depth > best:
                best = depth
            for v in kids.get(u, []):
                stack.append((v, depth + 1))
    return best


def claim_ids_of(node: dict[str, Any]) -> list[str]:
    raw = node.get("claim_ids") or []
    ids = [str(x) for x in raw if str(x).strip()]
    if ids:
        return ids
    nid = str(node.get("id") or "").strip()
    return [nid] if nid else []


def resolve_cost(node_id: str, costs: dict[str, Any]) -> tuple[int, str, str | None]:
    rec = costs.get(node_id)
    if not isinstance(rec, dict):
        raise RankError("asserted-cost-without-band", f"{node_id} missing cost")
    basis = str(rec.get("basis") or rec.get("cost_basis") or "").upper()
    if basis == "ESTIMATE":
        band = str(rec.get("band") or rec.get("estimate_band") or "").upper()
        if not band:
            raise RankError("asserted-cost-without-band", node_id)
        if band not in ESTIMATE_BAND_SECONDS:
            raise RankError("asserted-cost-without-band", f"{node_id} band={band}")
        return ESTIMATE_BAND_SECONDS[band], "ESTIMATE", band
    if basis == "DERIVED":
        try:
            seconds = int(rec.get("seconds") or rec.get("cost_seconds") or 0)
        except (TypeError, ValueError) as exc:
            raise RankError("asserted-cost-without-band", f"{node_id} {exc}") from exc
        if seconds <= 0:
            raise RankError("asserted-cost-without-band", f"{node_id} non-positive cost")
        return seconds, "DERIVED", None
    raise RankError("asserted-cost-without-band", f"{node_id} basis={basis or '<empty>'}")


def subtree_claims(
    intervention_id: str,
    nodes_by_id: dict[str, dict[str, Any]],
    kids: dict[str, list[str]],
) -> list[str]:
    claims: list[str] = []
    seen: set[str] = set()
    for did in descendants(intervention_id, kids):
        node = nodes_by_id.get(did)
        if not node:
            continue
        for cid in claim_ids_of(node):
            if cid not in seen:
                seen.add(cid)
                claims.append(cid)
    claims.sort()
    return claims


def nearest_cause(
    intervention_id: str,
    nodes_by_id: dict[str, dict[str, Any]],
    parents: dict[str, list[str]],
) -> str:
    seen = {intervention_id}
    q = deque([intervention_id])
    causes: list[str] = []
    while q:
        u = q.popleft()
        node = nodes_by_id.get(u)
        if node and node.get("type") == "CAUSE":
            causes.append(u)
        for p in parents.get(u, []):
            if p not in seen:
                seen.add(p)
                q.append(p)
    if not causes:
        return intervention_id
    causes.sort()
    return causes[0]


def rank_interventions(
    hierarchy: dict[str, Any],
    costs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = [n for n in (hierarchy.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    edges = [e for e in (hierarchy.get("edges") or []) if isinstance(e, dict)]
    if len(nodes) < 4:
        raise RankError("empty-subtree", "hierarchy too small")
    assert_acyclic(nodes, edges)
    nodes_by_id = {str(n["id"]): n for n in nodes}
    kids = children_map(edges)
    parents: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        p, c = str(e.get("parent") or ""), str(e.get("child") or "")
        if p and c:
            parents[c].append(p)
    cost_table = costs if isinstance(costs, dict) else (hierarchy.get("costs") or {})
    ranking: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    candidates = [n for n in nodes if n.get("type") in CANDIDATE_TYPES]
    for node in candidates:
        nid = str(node["id"])
        try:
            claims = subtree_claims(nid, nodes_by_id, kids)
            prevented_nodes = [nodes_by_id[d] for d in descendants(nid, kids) if d in nodes_by_id]
            if not claims or not prevented_nodes:
                rejected.append({"intervention_id": nid, "class": "empty-subtree"})
                continue
            sev = max_severity([str(n.get("severity") or "") for n in prevented_nodes])
            cost_s, basis, band = resolve_cost(nid, cost_table)
            iv_phase = str(node.get("phase") or "")
            iv_idx = phase_index(iv_phase)
            finding_phases = [str(n.get("phase") or "") for n in prevented_nodes]
            min_find = min(phase_index(p) for p in finding_phases)
            if iv_idx > min_find:
                rejected.append(
                    {
                        "intervention_id": nid,
                        "class": "phase-anachronism",
                        "intervention_phase": iv_phase,
                        "earliest_finding_phase": PHASE_ORDER[min_find],
                    }
                )
                continue
            weight = severity_weight(sev)
            score_micro = (len(claims) * weight * 1_000_000) // cost_s
            cause_id = nearest_cause(nid, nodes_by_id, parents)
            spec = str(node.get("spec_line") or hierarchy.get("default_spec_line") or "")
            if not spec:
                spec = f"WORK-UNIT-CATALOG.json#{nid}"
            ranking.append(
                {
                    "cause_id": cause_id,
                    "intervention_id": nid,
                    "action": str(node.get("title") or nid),
                    "available_at_phase": iv_phase,
                    "spec_line": spec,
                    "prevented_claim_ids": claims,
                    "subtree_size": len(claims),
                    "severity": sev,
                    "severity_weight": weight,
                    "cost_seconds": cost_s,
                    "cost_basis": basis,
                    "estimate_band": band,
                    "score_micro": score_micro,
                    "sort_key": [-score_micro, iv_idx, cost_s, nid],
                }
            )
        except RankError as exc:
            rejected.append(
                {
                    "intervention_id": nid,
                    "class": exc.classification,
                    "detail": exc.detail,
                }
            )

    ranking.sort(key=lambda r: (r["sort_key"][0], r["sort_key"][1], r["sort_key"][2], r["sort_key"][3]))
    for i, row in enumerate(ranking, 1):
        row["rank"] = i
        row["sort_key"] = [
            int(row["sort_key"][0]),
            int(row["sort_key"][1]),
            int(row["sort_key"][2]),
            str(row["sort_key"][3]),
        ]
    return {
        "ranking": ranking,
        "rejected": rejected,
        "max_depth": max_depth(nodes, edges),
        "acyclic": True,
        "candidate_count": len(candidates),
        "ranked_count": len(ranking),
    }


def ranking_ids(result: dict[str, Any]) -> list[str]:
    return [str(r["intervention_id"]) for r in result.get("ranking") or []]
