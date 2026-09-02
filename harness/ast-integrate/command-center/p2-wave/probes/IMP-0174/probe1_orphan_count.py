#!/usr/bin/env python3
"""Probe 1: computed orphan_count == 0 on the control extraction (not sampled)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import (  # noqa: E402
    ART,
    every_node_anchored,
    live_graph,
    merge_happened,
)
from workflow_foundry.tests.test_component_graph import run_all  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0174-probe1 {msg}")
    return 1


def main() -> int:
    lib = run_all()
    if not lib["pass"]:
        print(json.dumps(lib, indent=2, sort_keys=True)[:4000])
        return fail("library tests")

    graph = live_graph()
    stats = graph["stats"]
    n_orphan = int(graph["orphan_count"])
    n_nodes = int(stats["node_count"])
    n_stages = int(stats["stage_observations"])

    if n_nodes < 1:
        return fail("empty graph")
    if n_orphan != 0:
        return fail(f"orphan_count={n_orphan} want=0 ids={graph.get('orphan_ids')}")
    if n_stages != sum(len(n.get("provenance") or []) for n in graph["nodes"]):
        return fail("stage_observations is not a computed sum of provenance")
    if not every_node_anchored(graph):
        return fail("a node lacks candidate+resolvable source_span")
    if not merge_happened(graph):
        return fail("control fixture did not collapse a reused (kind, contract)")
    if n_stages <= n_nodes:
        return fail(f"no collapse: stages={n_stages} nodes={n_nodes}")
    if stats["orphan_count"] != n_orphan:
        return fail("stats.orphan_count disagrees with computed orphan_count")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {doc.get('state')}")
        if "SUCCESS:IMP-0174" not in text:
            return fail("receipt sentinel-absent")
        claimed = ((doc.get("graph") or {}).get("orphan_count"))
        if claimed != n_orphan:
            return fail(f"receipt orphan_count={claimed} live={n_orphan}")

    payload = {
        "probe": "probe1-orphan-count",
        "unit_id": "IMP-0174",
        "orphan_count": n_orphan,
        "node_count": n_nodes,
        "edge_count": stats["edge_count"],
        "stage_observations": n_stages,
        "collapsed": stats["collapsed"],
        "every_node_anchored": True,
        "merge_happened": True,
        "library_pass": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"orphan_count={n_orphan} nodes={n_nodes} stages={n_stages} collapsed={stats['collapsed']}")
    print("SUCCESS:IMP-0174-probe1 orphan-component count == 0 (computed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
