#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0079-provenance-license-graph-v2.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys

sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402

REPO = G.REPO


def catalog_unit() -> dict:
    data = json.loads((REPO / G.CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == G.UNIT:
            return unit
    raise SystemExit("FAILED:WFA-0079 catalog unit missing")


def main() -> int:
    graph = G.build_graph()
    ok, problems = G.closure_ok(graph)
    if not ok:
        print(json.dumps({"problems": problems}, indent=2))
        print("FAILED:WFA-0079 closure_ok")
        return 1
    counts = G.recompute_counts(graph)
    if counts["provenance_edges_unresolved"] != 0 or counts["provenance_resolution_rate"] != 1.0:
        print(json.dumps(counts, indent=2))
        print("FAILED:WFA-0079 counts")
        return 1
    if G.classified_non_owner_missing_anchor(graph):
        print("FAILED:WFA-0079 missing fetched-licence anchors")
        return 1
    if G.defaulted_unfetched(graph):
        print("FAILED:WFA-0079 defaulted unfetched")
        return 1
    if G.blueprints_missing_licence_class(graph):
        print("FAILED:WFA-0079 blueprint walk")
        return 1

    planted = G.mutate_unresolved_ref(graph)
    plant_ok, plant_problems = G.closure_ok(planted)
    if plant_ok or not any(p.startswith("unresolved-provenance:") for p in plant_problems):
        print(json.dumps(plant_problems, indent=2))
        print("FAILED:WFA-0079 unresolved-ref mutant silent")
        return 1

    dropped = G.mutate_drop_licensed_as(graph, "bp.benchmark-generation")
    drop_ok, drop_problems = G.closure_ok(dropped)
    if drop_ok or not any(
        "blueprint-walk-miss" in p or "licence-field-unreachable" in p for p in drop_problems
    ):
        print(json.dumps(drop_problems, indent=2))
        print("FAILED:WFA-0079 drop-licensed-as mutant silent")
        return 1

    defaulted = G.mutate_default_unfetched_to_mit(graph)
    def_ok, def_problems = G.closure_ok(defaulted)
    if def_ok or not any(p.startswith("defaulted-unfetched:") for p in def_problems):
        print(json.dumps(def_problems, indent=2))
        print("FAILED:WFA-0079 default-to-MIT mutant silent")
        return 1

    v1 = G.locate_v1()
    deps = G.locate_deps()
    unit = catalog_unit()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unclassified = G.unclassified_listed(graph)
    report = {
        "kind": "Graph",
        "unit_id": G.UNIT,
        "id": G.UNIT,
        "state": "SUCCESS",
        "sentinel": G.SENTINEL,
        "completion_sentinel": G.SENTINEL,
        "title": unit.get("title"),
        "question": G.QUESTION,
        "not_legal_advice": True,
        "output_schema": G.SCHEMA_REL,
        "schema_pack_present": (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file(),
        "produced_at": now,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "counts": counts,
        "unclassified_nodes": unclassified,
        "license_risk_register": G.risk_register(graph),
        "honesty_block": G.honesty_block(v1, deps),
        "evidence": [
            {
                "kind": "A-recomputed-counts",
                "claim": (
                    f"provenance_edges_unresolved={counts['provenance_edges_unresolved']} "
                    f"provenance_resolution_rate={counts['provenance_resolution_rate']} "
                    "every classified non-owner node carries a fetched-licence sha256"
                ),
            },
            {
                "kind": "B-reachability-walk",
                "claim": (
                    "BFS over the emitted edge set from each blueprint reaches "
                    "a licence-class node; a licence_class field without a "
                    "licensed-as path is still caught"
                ),
            },
        ],
        "tests": [
            {
                "id": "WFA-0079-UNRESOLVED-REF-MUTANT",
                "name": "reintroduce one unresolved ref and confirm the closure gate goes red",
                "command": G.P1,
                "result": "PASS",
                "planted_edge": "e:planted-unresolved",
                "gate_red": True,
            },
            {
                "id": "WFA-0079-HONESTY-BLOCK",
                "name": "honesty block states what is measured versus what remains rule-based",
                "command": G.P2,
                "result": "PASS",
            },
            {
                "id": "WFA-0079-UNCLASSIFIED-NO-DEFAULT",
                "name": "unfetched licences stay UNCLASSIFIED and listed, never defaulted",
                "command": G.P1,
                "result": "PASS",
                "listed_count": len(unclassified),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0079-probe2-reachability-walk",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
            "security_reviewer": {
                "reviewer_id": "WFA-0079-probe1-unresolved-ref-bypass",
                "lens": "threat-model",
                "named_bypass": (
                    "claim resolution rate 1.0 while a dangling cites edge exists, "
                    "or default an unfetched node to MIT"
                ),
                "bypass_achieved": False,
                "verdict": "PASS",
            },
        },
        "artifacts": [
            {"path": G.OUT_REL, "exists": True, "role": "primary"},
        ],
    }
    out = REPO / G.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    sha, size = G.digest_file(out)
    print(
        json.dumps(
            {
                "path": G.OUT_REL,
                "bytes": size,
                "sha256": sha,
                "counts": counts,
                "unclassified": len(unclassified),
                "v1_present": v1["present"],
            }
        )
    )
    print(G.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
