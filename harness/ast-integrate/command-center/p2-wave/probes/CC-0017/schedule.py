"""Recompute the 1->2 schedule lever from an explicit edge list.

PHASE-GRAPH.json is absent on this worktree. The authored critical-path
fragment survives only as CC-0016 catalog text. This module treats that
fragment as the edge list and recomputes; it does not restate 224 / 11->10.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EDGES_REL = "command-center/p2-wave/probes/CC-0017/fixtures/phase-edges.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PHASE_GRAPH = REPO / "command-center" / "PHASE-GRAPH.json"
RECORDED_PATH = ["0", "1", "2", "3", "4", "7", "7A", "10", "11", "14", "15"]
CONTESTED = "CONTESTED-1"


def load_edges(path: Path | None = None) -> dict[str, Any]:
    src = path or (REPO / EDGES_REL)
    return json.loads(src.read_text(encoding="utf-8"))


def longest_hard_path(edges: list[dict[str, Any]]) -> list[str]:
    adj: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for edge in edges:
        frm = str(edge["from"])
        to = str(edge["to"])
        nodes.add(frm)
        nodes.add(to)
        if str(edge.get("hardness") or "").upper() == "HARD":
            adj[frm].append(to)
    memo: dict[str, list[str]] = {}
    visiting: set[str] = set()

    def dfs(node: str) -> list[str]:
        if node in visiting:
            raise ValueError(f"hard-edge-cycle-at:{node}")
        if node in memo:
            return memo[node]
        visiting.add(node)
        best = [node]
        for nxt in adj.get(node, []):
            cand = [node] + dfs(nxt)
            if len(cand) > len(best):
                best = cand
        visiting.remove(node)
        memo[node] = best
        return best

    best: list[str] = []
    for node in nodes:
        cand = dfs(node)
        if len(cand) > len(best):
            best = cand
    return best


def with_contested_hardness(edges: list[dict[str, Any]], hardness: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for edge in edges:
        row = dict(edge)
        if str(row.get("id") or "") == CONTESTED or (
            str(row.get("from")) == "1" and str(row.get("to")) == "2"
        ):
            row["hardness"] = hardness
        out.append(row)
    return out


def catalog_release_counts() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = [u for u in (data.get("work_units") or []) if isinstance(u, dict)]
    phase2 = [u for u in units if str(u.get("phase")) == "2"]
    res = [u for u in units if str(u.get("id") or "").startswith("RES-")]
    b03 = [u for u in units if "B03" in (u.get("dependencies") or [])]
    dep17 = [u for u in units if "CC-0017" in (u.get("dependencies") or [])]
    dep_res0001 = [u for u in units if "RES-0001" in (u.get("dependencies") or [])]
    return {
        "work_units": len(units),
        "phase_2": len(phase2),
        "res_prefix": len(res),
        "depend_on_B03": len(b03),
        "depend_on_CC-0017": len(dep17),
        "depend_on_RES-0001": len(dep_res0001),
        "query_phase_2": "sum(1 for u in work_units if str(u.phase)=='2')",
        "query_res": "sum(1 for u in work_units if id.startswith('RES-'))",
        "query_b03": "sum(1 for u in work_units if 'B03' in dependencies)",
    }


def recompute() -> dict[str, Any]:
    doc = load_edges()
    edges = list(doc.get("edges") or [])
    before_edges = with_contested_hardness(edges, "HARD")
    after_edges = with_contested_hardness(edges, "SOFT")
    before = longest_hard_path(before_edges)
    after = longest_hard_path(after_edges)
    counts = catalog_release_counts()
    recorded_nodes = list(doc.get("critical_path_recorded") or RECORDED_PATH)
    return {
        "phase_graph_present": PHASE_GRAPH.is_file(),
        "edge_list_source": doc.get("source"),
        "edge_count": len(edges),
        "contested_edge": CONTESTED,
        "recorded_path": recorded_nodes,
        "recorded_node_count": len(recorded_nodes),
        "before": {
            "contested_hardness": "HARD",
            "path": before,
            "nodes": len(before),
        },
        "after": {
            "contested_hardness": "SOFT",
            "path": after,
            "nodes": len(after),
        },
        "catalog_claim": {
            "units_released": 224,
            "critical_path_nodes": [11, 10],
            "restated": False,
        },
        "released_recomputed": counts,
        "catalog_224_reproduced": counts["phase_2"] == 224 or counts["res_prefix"] == 224,
        "catalog_11_to_10_reproduced": len(before) == 11 and len(after) == 10,
        "delta_nodes": len(before) - len(after),
    }
