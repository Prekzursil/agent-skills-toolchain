#!/usr/bin/env python3
"""IMP-0173: duplicate collapse that aliases rows instead of deleting them.

Contract (catalog IMP-0173):
  * collapse duplicates into a canonical row
  * KEEP every duplicate-of edge and the losing row's provenance
  * the pre-collapse candidate set is reconstructible from the post-collapse graph
  * rank uses independent evidence and decision impact, never repetition count
"""
from __future__ import annotations

import copy
import json
from collections import defaultdict
from typing import Any

# Names the ranking function is forbidden to take. Shared with probe2 so the
# AST/param assertion and the implementation agree on the vocabulary.
FORBIDDEN_RANK_INPUTS = frozenset(
    {
        "count",
        "repetition",
        "repetition_count",
        "n_sources",
        "n_agents",
        "echo_count",
        "source_count",
        "times_seen",
        "frequency",
        "votes",
        "how_many_repeated",
    }
)

ORIGIN_FIELDS = (
    "id",
    "mechanism_fingerprint",
    "canonical_mechanism",
    "provenance",
    "independent_evidence",
    "decision_impact",
    "cross_domain",
    "repetition_count",
    "duplicate_of",
    "payload",
)


def rank_row(
    independent_evidence: float,
    decision_impact: float,
    cross_domain: float = 0.0,
) -> float:
    """Rank from independent evidence and decision impact, not from echo count.

    Inputs are scalars. A row dict (which may carry `repetition_count`) is not
    accepted, so the count field cannot enter this function even by accident.
    """
    return (
        float(independent_evidence) * 4.0
        + float(decision_impact) * 3.0
        + float(cross_domain) * 2.0
    )


def freeze_candidate(candidate: dict[str, Any]) -> str:
    """Stable identity of one pre-collapse candidate for set equality."""
    slim = {k: copy.deepcopy(candidate.get(k)) for k in ORIGIN_FIELDS}
    return json.dumps(slim, sort_keys=True, separators=(",", ":"), default=str)


def origin_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    return {k: copy.deepcopy(candidate.get(k)) for k in ORIGIN_FIELDS}


def _find(parent: dict[str, str], x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: dict[str, str], a: str, b: str) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


def cluster_candidates(candidates: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Same mechanism fingerprint, or an existing duplicate-of edge, is one cluster."""
    by_id = {c["id"]: c for c in candidates}
    if len(by_id) != len(candidates):
        dup = [c["id"] for c in candidates]
        raise ValueError(f"duplicate candidate ids: {dup}")
    parent = {i: i for i in by_id}
    by_fp: dict[str, list[str]] = defaultdict(list)
    for c in candidates:
        by_fp[str(c["mechanism_fingerprint"])].append(c["id"])
    for ids in by_fp.values():
        head = ids[0]
        for other in ids[1:]:
            _union(parent, head, other)
    for c in candidates:
        for tgt in c.get("duplicate_of") or []:
            if tgt in by_id:
                _union(parent, c["id"], str(tgt))
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        buckets[_find(parent, c["id"])].append(c)
    return list(buckets.values())


def pick_canonical(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [
        (
            rank_row(
                independent_evidence=float(row["independent_evidence"]),
                decision_impact=float(row["decision_impact"]),
                cross_domain=float(row.get("cross_domain") or 0.0),
            ),
            row["id"],
            row,
        )
        for row in cluster
    ]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return scored[0][2]


def union_payloads(
    cluster: list[dict[str, Any]], winner_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    winner = next(r for r in cluster if r["id"] == winner_id)
    merged = copy.deepcopy(winner.get("payload") or {})
    conflicts: list[dict[str, Any]] = []
    for row in cluster:
        for key, val in (row.get("payload") or {}).items():
            if key not in merged:
                merged[key] = copy.deepcopy(val)
            elif merged[key] != val:
                conflicts.append(
                    {"id": row["id"], "field": key, "canonical": merged[key], "other": val}
                )
    return merged, conflicts


def retained_duplicate_of_edges(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in candidates:
        src = row["id"]
        for tgt in row.get("duplicate_of") or []:
            key = (src, str(tgt))
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "from": src,
                    "to": str(tgt),
                    "kind": "duplicate-of",
                    "retained": True,
                    "via": "pre-collapse",
                }
            )
    return edges


def collapse_duplicates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Alias duplicates onto a canonical row. Never delete an id.

    Post-collapse graph:
      rows     – one row per pre-collapse candidate (status canonical|aliased)
      edges    – every pre-collapse duplicate-of edge, plus collapse edges
      trail    – one append-only record per cluster that actually collapsed
    Each row keeps `origin` so reconstruct_pre_collapse can rebuild the set.
    """
    if not candidates:
        return {"rows": [], "edges": [], "trail": [], "canonical_ids": []}

    pre_edges = retained_duplicate_of_edges(candidates)
    rows: list[dict[str, Any]] = []
    new_edges: list[dict[str, Any]] = []
    trail: list[dict[str, Any]] = []
    seen_edge: set[tuple[str, str]] = {(e["from"], e["to"]) for e in pre_edges}

    for cluster in cluster_candidates(candidates):
        winner = pick_canonical(cluster)
        payload_union, conflicts = union_payloads(cluster, winner["id"])
        lineage = [copy.deepcopy(r.get("provenance") or {}) for r in cluster]
        absorbed = [r["id"] for r in cluster if r["id"] != winner["id"]]
        if absorbed:
            trail.append(
                {
                    "surviving_id": winner["id"],
                    "absorbed_ids": absorbed,
                    "deciding_signals": {
                        "rank_inputs": [
                            "independent_evidence",
                            "decision_impact",
                            "cross_domain",
                        ],
                        "winner_score": rank_row(
                            independent_evidence=float(winner["independent_evidence"]),
                            decision_impact=float(winner["decision_impact"]),
                            cross_domain=float(winner.get("cross_domain") or 0.0),
                        ),
                        "ignored_repetition_counts": {
                            r["id"]: r.get("repetition_count") for r in cluster
                        },
                    },
                    "preserved_union": {
                        "provenance_lineage": lineage,
                        "payload": payload_union,
                        "payload_conflicts": conflicts,
                    },
                }
            )
        for row in cluster:
            origin = origin_snapshot(row)
            status = "canonical" if row["id"] == winner["id"] else "aliased"
            graph_row = {
                "id": row["id"],
                "status": status,
                "canonical_id": winner["id"],
                "mechanism_fingerprint": row["mechanism_fingerprint"],
                "canonical_mechanism": row.get("canonical_mechanism"),
                "provenance": copy.deepcopy(row.get("provenance") or {}),
                "lineage": lineage if status == "canonical" else [copy.deepcopy(row.get("provenance") or {})],
                "payload": copy.deepcopy(row.get("payload") or {}),
                "payload_union": payload_union if status == "canonical" else copy.deepcopy(row.get("payload") or {}),
                "origin": origin,
                "duplicate_of": list(row.get("duplicate_of") or []),
                "rank": rank_row(
                    independent_evidence=float(row["independent_evidence"]),
                    decision_impact=float(row["decision_impact"]),
                    cross_domain=float(row.get("cross_domain") or 0.0),
                ),
                "repetition_count_recorded_not_ranked": row.get("repetition_count"),
            }
            if status == "aliased":
                if winner["id"] not in graph_row["duplicate_of"]:
                    graph_row["duplicate_of"] = list(graph_row["duplicate_of"]) + [
                        winner["id"]
                    ]
                key = (row["id"], winner["id"])
                if key not in seen_edge:
                    seen_edge.add(key)
                    new_edges.append(
                        {
                            "from": row["id"],
                            "to": winner["id"],
                            "kind": "duplicate-of",
                            "retained": False,
                            "via": "collapse",
                        }
                    )
            rows.append(graph_row)

    rows.sort(key=lambda r: r["id"])
    edges = pre_edges + new_edges
    edges.sort(key=lambda e: (e["from"], e["to"], e["via"]))
    return {
        "rows": rows,
        "edges": edges,
        "trail": trail,
        "canonical_ids": sorted(r["id"] for r in rows if r["status"] == "canonical"),
        "aliased_ids": sorted(r["id"] for r in rows if r["status"] == "aliased"),
    }


def reconstruct_pre_collapse(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild the pre-collapse candidate records from origin snapshots only."""
    rebuilt: list[dict[str, Any]] = []
    for row in graph.get("rows") or []:
        origin = row.get("origin")
        if not isinstance(origin, dict) or "id" not in origin:
            raise ValueError(f"graph row {row.get('id')!r} has no origin snapshot")
        rebuilt.append(copy.deepcopy(origin))
    rebuilt.sort(key=lambda c: c["id"])
    return rebuilt


def pre_collapse_set(candidates: list[dict[str, Any]]) -> set[str]:
    return {freeze_candidate(c) for c in candidates}


def reconstructed_set(graph: dict[str, Any]) -> set[str]:
    return {freeze_candidate(c) for c in reconstruct_pre_collapse(graph)}


def sets_equal(
    candidates: list[dict[str, Any]], graph: dict[str, Any]
) -> dict[str, Any]:
    left = pre_collapse_set(candidates)
    right = reconstructed_set(graph)
    return {
        "equal": left == right,
        "pre_collapse_n": len(left),
        "reconstructed_n": len(right),
        "missing_from_graph": sorted(left - right),
        "extra_in_graph": sorted(right - left),
        "pre_collapse_ids": sorted(c["id"] for c in candidates),
        "reconstructed_ids": [c["id"] for c in reconstruct_pre_collapse(graph)],
    }


def collapse_lossy_delete(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Planted broken cousin: drop aliased rows. Reconstruction must fail."""
    graph = collapse_duplicates(candidates)
    graph = copy.deepcopy(graph)
    graph["rows"] = [r for r in graph["rows"] if r["status"] == "canonical"]
    graph["lossy"] = True
    return graph


def load_candidates(path: Any) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc["candidates"] if isinstance(doc, dict) else doc
    if not isinstance(rows, list) or not rows:
        raise ValueError("candidates fixture empty")
    return rows
