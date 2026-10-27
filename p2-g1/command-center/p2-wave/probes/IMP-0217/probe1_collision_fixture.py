"""IMP-0217 probe 1 (source): colliding-internal-id fixture completes with two distinct receipts.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0217/probe1_collision_fixture.py
Exit 0 iff two sibling subworkflows sharing the SAME internal unit ids produce two
distinct receipts per id and two isolated artifact spaces.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.subworkflow_executor import Subworkflow, Task, Workflow, execute  # noqa: E402

shared = Workflow(
    id="shared-body",
    nodes=(Task(id="unit-a", budget=3), Task(id="unit-b", budget=2)),
)
parent = Workflow(
    id="parent",
    nodes=(
        Subworkflow(id="sibA", workflow_ref="shared-body", id_namespace="sibA",
                    param_bindings={"label": "from-A"}),
        Subworkflow(id="sibB", workflow_ref="shared-body", id_namespace="sibB",
                    param_bindings={"label": "from-B"}),
    ),
)

with tempfile.TemporaryDirectory() as td:
    res = execute(parent, {"shared-body": shared}, td, params={"label": "root"})
    receipts = sorted(res.receipts)
    unit_a = [r for r in receipts if r.endswith("::unit-a")]
    distinct_a = len(unit_a) == 2 and len(set(unit_a)) == 2
    spaces_isolated = (
        len(res.artifact_spaces) == 2
        and res.artifact_spaces["sibA"] != res.artifact_spaces["sibB"]
        and Path(res.artifact_spaces["sibA"]).is_dir()
        and Path(res.artifact_spaces["sibB"]).is_dir()
    )
    payloads = (
        Path(res.artifacts["sibA::unit-a"]).read_text(encoding="utf-8"),
        Path(res.artifacts["sibB::unit-a"]).read_text(encoding="utf-8"),
    )
    payloads_distinct = payloads == ("from-A", "from-B")
    ok = distinct_a and spaces_isolated and payloads_distinct

out = {
    "probe": "probe1-colliding-internal-ids",
    "unit_id": "IMP-0217",
    "receipts": receipts,
    "unit_a_receipts": unit_a,
    "two_distinct_unit_a_receipts": distinct_a,
    "artifact_spaces": sorted(res.artifact_spaces),
    "spaces_isolated": spaces_isolated,
    "payloads_sibA_sibB": list(payloads),
    "payloads_distinct": payloads_distinct,
    "pass": ok,
}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-collision.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0217-probe1 collision fixture did not hold")
    raise SystemExit(1)
print("SUCCESS:IMP-0217-probe1 colliding internal ids: two distinct receipts, isolated spaces")
