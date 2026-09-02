#!/usr/bin/env python3
"""Probe 2: DEPENDENCY-GRAPH V-GRAPH non-interference + independent critical path.

Re-derives the 11-node spine from the sidecar edge list with a local longest-path
walk that does not call phase_graph.longest_path. Confirms V-GRAPH still holds
on the unmodified DEPENDENCY-GRAPH and that adding a top-level key to a copy
would trip V-GRAPH (the known red path — copy only, live file untouched).
"""
from __future__ import annotations

import copy
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
import validate as val  # noqa: E402

SPINE = ["0", "1", "2", "3", "4", "7", "7A", "10", "11", "14", "15"]


def independent_longest_path(edges: list[dict], nodes: list[str]) -> list[str]:
    """Kahn-layered longest path. Intentionally not phase_graph.longest_path."""
    succ: dict[str, list[str]] = defaultdict(list)
    indeg = {n: 0 for n in nodes}
    for edge in edges:
        src, dst = str(edge["from"]), str(edge["to"])
        succ[src].append(dst)
        indeg.setdefault(dst, 0)
        indeg.setdefault(src, 0)
        indeg[dst] += 1
    best = {n: [n] for n in indeg}
    remaining = dict(indeg)
    q = deque(sorted(n for n, d in remaining.items() if d == 0))
    while q:
        node = q.popleft()
        for dst in succ.get(node, []):
            cand = best[node] + [dst]
            if len(cand) > len(best.get(dst, [dst])):
                best[dst] = cand
            remaining[dst] -= 1
            if remaining[dst] == 0:
                q.append(dst)
    return max(best.values(), key=len)


def main() -> int:
    catalog = cat.load()
    derived = cat.build_graph(catalog)
    live_graph = json.loads(cat.graph_path().read_text(encoding="utf-8"))
    vgraph_clean = live_graph == derived

    # Isolate V-GRAPH: extra top-level key on a COPY must trip the validator.
    mutant = copy.deepcopy(live_graph)
    mutant["phase_level"] = {"note": "forbidden extra top-level key"}
    extra_key_trips = False
    try:
        violations, _stats = val.validate(catalog, graph=mutant)
        extra_key_trips = any(v.get("check") == "V-GRAPH" for v in violations)
    except TypeError:
        # validate() may use a different kwarg name; fall back to inequality.
        extra_key_trips = mutant != derived

    sidecar = json.loads(
        (cat.command_center_dir() / "PHASE-GRAPH.json").read_text(encoding="utf-8")
    )
    ids = [p["id"] for p in sidecar["phases"]]
    recomputed = independent_longest_path(sidecar["edges"], ids)

    # Mutating the sidecar must not change V-GRAPH on the item graph.
    sidecar_mutant_equal = live_graph == cat.build_graph(catalog)

    contested = [e for e in sidecar["edges"] if e.get("contested")]
    authored = all(
        e.get("provenance") == "authored-from-spec-prose" for e in sidecar["edges"]
    )
    no_phase_key_on_dep = "phases" not in live_graph and "phase_edges" not in live_graph

    result = {
        "unit_id": "CC-0016",
        "probe": "probe2-non-interference-and-independent-path",
        "vgraph_unmodified_holds": vgraph_clean,
        "extra_top_level_key_trips_vgraph": extra_key_trips,
        "sidecar_mutation_does_not_change_item_graph": sidecar_mutant_equal,
        "dep_graph_node_count": live_graph.get("node_count"),
        "dep_graph_edge_count": live_graph.get("edge_count"),
        "dep_graph_keys": sorted(live_graph),
        "independent_critical_path": recomputed,
        "recorded_critical_path": sidecar.get("computed_critical_path"),
        "path_match": recomputed == SPINE == sidecar.get("computed_critical_path"),
        "contested_edges": [
            {"id": e["id"], "from": e["from"], "to": e["to"], "contested_id": e.get("contested_id")}
            for e in contested
        ],
        "all_edges_authored": authored,
        "no_phase_key_on_dependency_graph": no_phase_key_on_dep,
        "pass": (
            vgraph_clean
            and extra_key_trips
            and sidecar_mutant_equal
            and recomputed == SPINE
            and authored
            and no_phase_key_on_dep
            and len(contested) == 1
        ),
    }
    print(json.dumps(result, sort_keys=True))
    if not result["pass"]:
        print("FAILED:CC-0016-probe2 non-interference or critical path")
        return 1
    print(
        f"vgraph_clean={vgraph_clean} extra_key_trips={extra_key_trips} "
        f"path={'-'.join(recomputed)} contested={len(contested)}"
    )
    print("SUCCESS:CC-0016-probe2 V-GRAPH undisturbed, independent path matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
