"""Semantic component graph over extracted stages/roles/gates."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


class OrphanComponentError(Exception):
    def __init__(self, error_id: str, message: str = "") -> None:
        self.error_id = error_id
        super().__init__(message or error_id)


def span_is_resolvable(span: Any) -> bool:
    if not isinstance(span, dict):
        return False
    uri = span.get("uri")
    start_line = span.get("start_line")
    return isinstance(uri, str) and bool(uri.strip()) and isinstance(start_line, int) and start_line >= 1


def valid_provenance(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    cid = row.get("candidate_id")
    if not isinstance(cid, str) or not cid.strip():
        return False
    return span_is_resolvable(row.get("source_span"))


def is_orphan(node: Any) -> bool:
    if not isinstance(node, dict):
        return True
    prov = node.get("provenance")
    if not isinstance(prov, list) or not prov:
        return True
    return not any(valid_provenance(p) for p in prov)


def orphan_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in (graph.get("nodes") or []) if is_orphan(n)]


def orphan_count(graph: dict[str, Any]) -> int:
    return len(orphan_nodes(graph))


def assert_no_orphans(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = orphan_nodes(graph)
    if nodes:
        raise OrphanComponentError("orphan-component", f"n={len(nodes)}")
    return graph


def _node_key(kind: str, contract: dict[str, Any]) -> tuple:
    return (
        kind,
        json_stable(contract),
    )


def json_stable(obj: Any) -> str:
    import json
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def assemble(extraction: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[tuple, dict[str, Any]] = {}
    collapsed = 0
    stage_obs = 0
    for cand in extraction.get("candidates") or []:
        cid = str(cand.get("id") or "")
        for stage in cand.get("stages") or []:
            stage_obs += 1
            kind = str(stage.get("kind") or stage.get("local_id") or "stage")
            contract = dict(stage.get("contract") or {})
            key = _node_key(kind, contract)
            span = dict(stage.get("source_span") or {})
            prov = {
                "candidate_id": cid,
                "local_id": stage.get("local_id"),
                "source_span": span,
            }
            if key in nodes:
                nodes[key]["provenance"].append(prov)
                collapsed += 1
            else:
                nodes[key] = {
                    "id": f"{kind}:{len(nodes):03d}",
                    "kind": kind,
                    "contract": contract,
                    "provenance": [prov],
                }
    node_list = list(nodes.values())
    n_orphan = orphan_count({"nodes": node_list})
    n_edges = 0
    for cand in extraction.get("candidates") or []:
        n_edges += len(cand.get("compositions") or [])
    return {
        "nodes": node_list,
        "stats": {
            "node_count": len(node_list),
            "stage_observations": stage_obs,
            "collapsed": collapsed,
            "orphan_count": n_orphan,
            "edge_count": n_edges,
        },
        "orphan_count": n_orphan,
        "edge_count": n_edges,
        "orphan_ids": [n["id"] for n in node_list if is_orphan(n)],
    }


def build(extraction: dict[str, Any]) -> dict[str, Any]:
    graph = assemble(extraction)
    assert_no_orphans(graph)
    return graph


def graph_public(graph: dict[str, Any]) -> dict[str, Any]:
    return dict(graph)


def plant_orphan(graph: dict[str, Any]) -> dict[str, Any]:
    g = deepcopy(graph)
    g.setdefault("nodes", []).append(
        {
            "id": "planted-unanchored-stage",
            "kind": "float",
            "contract": {"output_type": "none"},
            "provenance": [],
        }
    )
    g["orphan_count"] = orphan_count(g)
    g["orphan_ids"] = [n["id"] for n in g["nodes"] if is_orphan(n)]
    return g


def with_unanchored_stage(extraction: dict[str, Any]) -> dict[str, Any]:
    doc = deepcopy(extraction)
    cands = doc.setdefault("candidates", [])
    if not cands:
        cands.append({"id": "cand-x", "stages": []})
    cands[0].setdefault("stages", []).append(
        {
            "local_id": "unanchored",
            "kind": "float",
            "source_span": {},
            "contract": {"output_type": "none"},
        }
    )
    return doc


def with_lookalike_named_orphan(extraction: dict[str, Any]) -> dict[str, Any]:
    doc = deepcopy(extraction)
    cands = doc.setdefault("candidates", [])
    if not cands:
        cands.append({"id": "cand-x", "stages": []})
    cands[0].setdefault("stages", []).append(
        {
            "local_id": "orphan-lookalike",
            "kind": "orphan-lookalike",
            "source_span": {"uri": "candidates/lookalike.yaml", "start_line": 1, "end_line": 2},
            "contract": {"output_type": "lookalike", "roles": ["none"], "tools": []},
        }
    )
    return doc
