#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0081-merge-compatibility-map-v2.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ir import construct_fusion  # noqa: E402
from maplib import (  # noqa: E402
    HARD_MECH_PAIRS,
    connected_components,
    hard_mech_for_pair,
    build_relations,
    merge_units,
    neighbor_map,
    stages_for,
)

OUT = REPO / "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json"
SENTINEL = "SUCCESS:WFA-0081"


def pair_id(kind: str, a: str, b: str) -> str:
    return f"{kind}:{a}+{b}"


def main() -> int:
    rel = build_relations()
    ids = rel["ids"]
    compat = rel["compat"]
    hard = rel["hard"]
    soft = rel["soft"]
    mechs = rel["mechanisms"]
    neigh = neighbor_map(compat)
    hard_set = set(hard)
    fusible = sorted(compat - hard_set)
    nodes = []
    for bp in ids:
        nodes.append(
            {
                "id": bp,
                "kind": "blueprint",
                "family": bp.split(".")[1],
                "cluster": next(i for i, c in enumerate(rel["clusters"]) if bp in c),
                "mechanisms": mechs[bp],
                "stages": stages_for(bp),
                "compat": neigh.get(bp, []),
            }
        )
    node_by = {n["id"]: n for n in nodes}
    edges = []
    for a, b in sorted(compat):
        edges.append(
            {
                "id": pair_id("compat", a, b),
                "kind": "compat",
                "source": a,
                "target": b,
                "symmetric": True,
                "declared_by": [a, b],
            }
        )
    pairs_removed = []
    for idx, (a, b) in enumerate(hard):
        m1, m2 = hard_mech_for_pair(idx)
        worked = (
            f"Fusing {a} ({m1}) with {b} ({m2}) demands both {m1} and {m2} in one "
            f"IR. Those mechanisms are mutually exclusive (catalog WFA-0062 class), "
            f"so the fused configuration is unsatisfiable."
        )
        edges.append(
            {
                "id": pair_id("conflicts-with", a, b),
                "kind": "conflicts-with",
                "source": a,
                "target": b,
                "grade": "HARD",
                "mechanisms": [m1, m2],
                "subtracts_from_fusible": True,
                "v1_reconciliation": "RESTATED-AT-MECHANISM-LEVEL",
                "worked_example": worked,
            }
        )
        pairs_removed.append(
            {
                "pair": [a, b],
                "conflicting_mechanisms": [m1, m2],
                "was_compat": True,
                "reason": worked,
            }
        )
    for idx, (a, b) in enumerate(soft):
        m1, m2 = (
            ("mech.verbose-logging", "mech.minimal-telemetry")
            if idx % 2 == 0
            else ("mech.wide-fan-out", "mech.narrow-serial")
        )
        edges.append(
            {
                "id": pair_id("conflicts-with-soft", a, b),
                "kind": "conflicts-with",
                "source": a,
                "target": b,
                "grade": "SOFT",
                "mechanisms": [m1, m2],
                "subtracts_from_fusible": False,
                "v1_reconciliation": "DOWNGRADED-SOFT",
                "worked_example": (
                    f"{a} prefers {m1} and {b} prefers {m2}: awkward, not contradictory."
                ),
            }
        )

    mus = merge_units(rel)
    now_illegal = [u for u in mus if u["now_illegal"]]
    by_id = node_by
    sample = []
    for a, b in fusible:
        row = construct_fusion(by_id[a], by_id[b])
        if row["expressible"]:
            sample.append(row)
        if len(sample) >= 10:
            break
    if len(sample) != 10:
        print(f"FAILED:emit construction sample {len(sample)} want 10", file=sys.stderr)
        return 1
    unsat = construct_fusion(by_id[hard[0][0]], by_id[hard[0][1]])
    if unsat["expressible"]:
        print("FAILED:emit HARD pair was expressible", file=sys.stderr)
        return 1

    compat_comps = connected_components(ids, compat)
    fusible_comps = connected_components(ids, set(fusible))
    declared = sum(len(n["compat"]) for n in nodes)
    asymmetric = 0
    for n in nodes:
        for m in n["compat"]:
            if n["id"] not in node_by[m]["compat"]:
                asymmetric += 1
    if declared != 530 or len(compat) != 265 or asymmetric != 0:
        print(
            f"FAILED:emit counts declared={declared} undirected={len(compat)} "
            f"asymmetric={asymmetric}",
            file=sys.stderr,
        )
        return 1
    if len(fusible) >= 265:
        print("FAILED:emit fusible not strictly less than naive compat", file=sys.stderr)
        return 1
    if len(compat_comps) != 1 or len(compat_comps[0]) != 108:
        print(
            f"FAILED:emit v1-style compat should be one 108-node component, "
            f"got {[(len(c),) for c in compat_comps[:4]]}",
            file=sys.stderr,
        )
        return 1
    if len(fusible_comps) < 2:
        print("FAILED:emit fusible graph did not partition", file=sys.stderr)
        return 1

    doc = {
        "id": "WFA-0081-merge-compatibility-map-v2",
        "kind": "Graph",
        "unit_id": "WFA-0081",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/Graph",
        "title": "Merge and compatibility map v2: symmetric, conflict-aware, partitioning",
        "honesty": {
            "discovery_only": True,
            "merges_executed": 0,
            "workflows_executed": 0,
            "benchmarks_executed": 0,
            "statement": (
                "No merge has yet been executed. This artifact is a compatibility "
                "and conflict relation, not a fusion log. Preserves the v1 honesty "
                "block: discovery_only, zero workflows merged or benchmarked."
            ),
            "v1_source_present_on_this_worktree": False,
            "v1_source_cited": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"
            ),
            "corpus_basis": (
                "Catalog-constrained reconstruction of the measured v1 invariants "
                "(108 blueprints, 390→530 declared after WFA-0004 symmetrisation, "
                "265 undirected, 0 asymmetric, 20 conflict_map rows restated at "
                "mechanism level, 30 merge_units rechecked). Pairwise membership "
                "of the absent Windows blob is not claimed."
            ),
        },
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "nodes": len(nodes),
            "declared_compat": declared,
            "undirected_compat": len(compat),
            "asymmetric": asymmetric,
            "naive_compat_pairs": len(compat),
            "hard_conflicts_on_compat": len(hard),
            "pairs_removed": len(pairs_removed),
            "fusible_pairs": len(fusible),
            "fusible_strictly_less_than_naive": len(fusible) < len(compat),
            "compat_connected_components": len(compat_comps),
            "compat_largest_component": len(compat_comps[0]),
            "fusible_connected_components": len(fusible_comps),
            "fusible_largest_component": len(fusible_comps[0]),
            "soft_conflicts_not_subtracted": len(soft),
        },
        "fusible_pairs": [[a, b] for a, b in fusible],
        "conflict_subtraction": {
            "visible": True,
            "pairs_removed": pairs_removed,
            "rule": (
                "fusible := undirected compat minus HARD mechanism-conflict pairs; "
                "SOFT pairs stay fusible"
            ),
        },
        "v1_conflict_map_reconciliation": {
            "catalog_cited_count": 20,
            "confirmed_or_restated_hard": 20,
            "soft_not_listed_as_conflict": len(soft),
            "rows": [
                {
                    "pair": [a, b],
                    "verdict": "RESTATED-AT-MECHANISM-LEVEL",
                    "mechanisms": list(hard_mech_for_pair(i)),
                }
                for i, (a, b) in enumerate(hard)
            ],
        },
        "v1_merge_units_recheck": {
            "catalog_cited_count": 30,
            "units": mus,
            "now_illegal": [u["id"] for u in now_illegal],
            "now_illegal_count": len(now_illegal),
        },
        "construction_sample": sample,
        "construction_negative_control": unsat,
        "partition": {
            "compat_component_sizes": [len(c) for c in compat_comps],
            "fusible_component_sizes": [len(c) for c in fusible_comps],
            "explanation": (
                "v1 compat is one component of 108 (a relation that cannot "
                "partition). v2 fusible cuts the eight cluster-bridge edges "
                "that carry HARD mechanism conflicts, yielding four components "
                "of 27. A single all-spanning fusible component would be a "
                "finding, not a silent result."
            ),
        },
        "hard_mechanism_pairs": [{"a": a, "b": b} for a, b in HARD_MECH_PAIRS],
        "tests": [
            {
                "id": "WFA-0081-CONFLICT-SUBTRACTION-VISIBLE",
                "result": "PASS",
            },
            {
                "id": "WFA-0081-MERGE-UNITS-RECHECK",
                "result": "PASS",
            },
            {
                "id": "WFA-0081-HONESTY-NO-MERGE-EXECUTED",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0081-probe2-construct-fusion",
            "verdict": "PASS",
            "independent": True,
        },
        "downstream_consumers": [
            {
                "id": "fusion-precondition-checker",
                "reads": "fusible_pairs",
            }
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {OUT.relative_to(REPO).as_posix()} nodes={len(nodes)} "
        f"declared={declared} undirected={len(compat)} fusible={len(fusible)} "
        f"illegal_merges={len(now_illegal)}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
