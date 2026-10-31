"""IMP-0174 probe 1 (source): orphan-component count == 0 on the real build.

Every component node of the assembled graph traces to at least one
candidate with a resolvable source span. Exit 0 iff the computed orphan
count is zero and every node carries valid provenance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_WALK = Path(__file__).resolve().parent
REPO = _WALK
for _ in range(6):
    if (_REPO_TEST := _WALK / "command-center" / "p2-wave").is_dir():
        REPO = _WALK
        break
    _WALK = _WALK.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.workflow_foundry.component_graph import (  # noqa: E402
    assemble,
    is_orphan,
    orphan_count,
    span_is_resolvable,
)

extraction = {
    "candidates": [
        {
            "id": "cand.master-branch-scan",
            "stages": [
                {"local_id": "s1", "kind": "ingest",
                 "source_span": {"uri": "sources/pipeline.md", "start_line": 10, "end_line": 18},
                 "contract": {"output_type": "rows", "roles": ["reader"]}},
                {"local_id": "s2", "kind": "plan",
                 "source_span": {"uri": "sources/pipeline.md", "start_line": 19, "end_line": 25},
                 "contract": {"output_type": "plan", "roles": ["planner"]}},
            ],
            "compositions": [["s1", "s2"]],
        },
        {
            "id": "cand.fork-scan",
            "stages": [
                {"local_id": "r1", "kind": "ingest",
                 "source_span": {"uri": "forks/x/pipeline.md", "start_line": 3, "end_line": 9},
                 "contract": {"output_type": "rows", "roles": ["reader"]}},
                {"local_id": "r2", "kind": "plan",
                 "source_span": {"uri": "forks/x/pipeline.md", "start_line": 10, "end_line": 16},
                 "contract": {"output_type": "plan", "roles": ["planner"]}},
            ],
            "compositions": [["r1", "r2"]],
        },
        {
            "id": "cand.audit-scan",
            "stages": [
                {"local_id": "a1", "kind": "gate",
                 "source_span": {"uri": "audits/digest.md", "start_line": 40, "end_line": 44},
                 "contract": {"output_type": "verdict", "roles": ["auditor"]}},
            ],
            "compositions": [],
        },
    ]
}

graph = assemble(extraction)
nodes = graph["nodes"]
collapsed_ingest = [n for n in nodes if n["kind"] == "ingest"]

checks = {
    "orphan_count_eq_0": graph["orphan_count"] == 0,
    "every_node_has_provenance": all(len(n.get("provenance") or []) >= 1 for n in nodes),
    "every_provenance_span_resolvable": all(
        span_is_resolvable(p.get("source_span"))
        for n in nodes for p in (n.get("provenance") or [])
    ),
    "identical_components_collapsed": len(collapsed_ingest) == 1
        and len(collapsed_ingest[0]["provenance"]) == 2,
    "node_traces_to_candidates": all(
        any(p.get("candidate_id") for p in (n.get("provenance") or [])) for n in nodes
    ),
    "edge_count_computed": graph["edge_count"] == 2,
    "no_orphan_ids": graph["orphan_ids"] == [],
    "detector_alive": is_orphan({"provenance": []}) is True
        and is_orphan({"provenance": [{"candidate_id": "c", "source_span": {}}]}) is True
        and is_orphan({"provenance": [{"candidate_id": "c",
                                       "source_span": {"uri": "a.md", "start_line": 1}}]}) is False,
}

result = {
    "probe": "probe1-orphan-count",
    "unit_id": "IMP-0174",
    "orphan_count": graph["orphan_count"],
    "stats": graph["stats"],
    "node_ids": [n["id"] for n in nodes],
    "checks": checks,
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0174-probe1 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0174-probe1 orphan component count == 0 (computed)")
