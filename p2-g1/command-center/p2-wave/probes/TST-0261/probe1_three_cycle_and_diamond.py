#!/usr/bin/env python3
"""TST-0261 probe 1: the planted 3-node cycle FIRES with its exact path; the
diamond is SILENT.

Both states in one run against the LIVE tools/council/evidence_graph.py:
  - three_node_cycle: status CYCLIC, fired, path_printed ==
    "claim-alpha -> claim-beta -> claim-gamma -> claim-alpha"
  - diamond (shared ancestor, no directed cycle): status ACYCLIC, cycles []
  - NC4: an independent UNDIRECTED union-find walk FLAGS the diamond while the
    directed support-cycle detector stays silent - proof the detector is
    genuinely directed, not an undirected leftover detector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import DIAMOND, THREE_NODE_CYCLE  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from council.evidence_graph import directed_support_cycles, inspect  # noqa: E402


def undirected_components_flags_cycle(graph: dict) -> bool:
    """Independent undirected walk (union-find): does ANY edge close a ring?"""
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    edges = list(graph.get("support") or []) + list(graph.get("contradiction") or [])
    for s, d in edges:
        for n in (s, d):
            parent.setdefault(n, n)
    fired = False
    for s, d in edges:
        rs, rd = find(s), find(d)
        if rs == rd:
            fired = True
        else:
            parent[rs] = rd
    return fired


def main() -> int:
    checks: dict[str, bool] = {}
    cyc = inspect(THREE_NODE_CYCLE)
    checks["three_cycle_fires"] = cyc["status"] == "CYCLIC" and cyc["fired"]
    expected_path = "claim-alpha -> claim-beta -> claim-gamma -> claim-alpha"
    got = (cyc["cycles"][0]["path_printed"] if cyc["cycles"] else "")
    checks["exact_path_printed"] = got == expected_path
    checks["three_cycle_graph_size"] = cyc["graph_size"] == {
        "nodes": 3, "edges": 3, "support_edges": 3, "contradiction_edges": 0,
    }
    dia = inspect(DIAMOND)
    checks["diamond_silent"] = dia["status"] == "ACYCLIC" and not dia["fired"] and dia["cycles"] == []
    checks["diamond_graph_size"] = dia["graph_size"] == {
        "nodes": 8, "edges": 8, "support_edges": 8, "contradiction_edges": 0,
    }
    checks["nc4_undirected_flags_diamond_directed_silent"] = (
        undirected_components_flags_cycle(DIAMOND) is True
        and inspect(DIAMOND)["fired"] is False
    )

    out = {
        "probe": "probe1_three_cycle_and_diamond",
        "unit": "TST-0261",
        "bad_state": {
            "graph": "three_node_cycle",
            "status": cyc["status"],
            "path_printed": got,
        },
        "good_state": {
            "graph": "diamond",
            "status": dia["status"],
            "cycle_count": len(dia["cycles"]),
        },
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-three-cycle-and-diamond.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
