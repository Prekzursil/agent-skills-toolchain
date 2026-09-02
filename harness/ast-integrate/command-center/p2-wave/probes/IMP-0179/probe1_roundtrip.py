#!/usr/bin/env python3
"""Named probe 1: lineage survives export/import by field-by-field equality.

Signal 1 is path-wise scalar equality of the lineage record.
Signal 2 is sha256 of the canonical lineage JSON.
Disagreement between those two readings is a failure, not a picked winner.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lineage import LineageError, lineage_graph, round_trip  # noqa: E402
from scenario import catalog  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0179.json"


def main() -> int:
    workflows = catalog()
    if len(workflows) < 5:
        print(f"FAILED:IMP-0179-probe1 catalog_size={len(workflows)} want>=5")
        return 1

    rows = []
    for workflow in workflows:
        try:
            rec = round_trip(workflow)
        except LineageError as exc:
            print(f"FAILED:IMP-0179-probe1 round-trip refused {workflow.get('workflow_id')}: {exc}")
            return 1
        if not rec["pass"]:
            print(f"FAILED:IMP-0179-probe1 lineage not equal {rec['workflow_id']}")
            print(json.dumps(rec, indent=2, default=str)[:3000])
            return 1
        rows.append(rec)

    graph = lineage_graph(workflows)
    if len(graph["edges"]) < 5:
        print(f"FAILED:IMP-0179-probe1 graph edges={len(graph['edges'])} want>=5")
        return 1
    licences = [
        n.get("licence")
        for n in graph["nodes"]
        if n.get("type") in {"component", "source"} and n.get("licence")
    ]
    if len(set(licences)) < 3:
        print(f"FAILED:IMP-0179-probe1 distinct licences={sorted(set(licences))} want>=3")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0179-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0179":
        print("FAILED:IMP-0179-probe1 unit_id", doc.get("unit_id"))
        return 1
    blob = json.dumps(doc, sort_keys=True)
    if "SUCCESS:IMP-0179" not in blob:
        print("FAILED:IMP-0179-probe1 sentinel absent")
        return 1
    recorded = {r["workflow_id"]: r for r in (doc.get("round_trip") or [])}
    if len(recorded) != len(rows):
        print(f"FAILED:IMP-0179-probe1 receipt round_trip rows={len(recorded)} live={len(rows)}")
        return 1
    for rec in rows:
        got = recorded.get(rec["workflow_id"])
        if not got:
            print(f"FAILED:IMP-0179-probe1 receipt missing {rec['workflow_id']}")
            return 1
        if got.get("sha256_before") != rec["sha256_before"]:
            print(f"FAILED:IMP-0179-probe1 sha drift {rec['workflow_id']}")
            return 1
        if got.get("field_equal") is not True:
            print(f"FAILED:IMP-0179-probe1 receipt field_equal not true {rec['workflow_id']}")
            return 1

    out = {
        "probe": "probe1-roundtrip",
        "unit_id": "IMP-0179",
        "workflows": len(rows),
        "all_field_equal": True,
        "all_sha256_match": True,
        "graph_nodes": len(graph["nodes"]),
        "graph_edges": len(graph["edges"]),
        "distinct_licences": sorted(set(licences)),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for rec in rows:
        print(
            f"workflow {rec['workflow_id']} field_equal={rec['field_equal']} "
            f"sha_match={rec['sha256_match']} fields={rec['field_count']}"
        )
    print("SUCCESS:IMP-0179-probe1 lineage round-trip field-by-field equality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
