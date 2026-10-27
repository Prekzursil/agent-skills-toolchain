"""IMP-0217 probe 2 (verifier): parent budget equals the sum of child budgets, no double count.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0217/probe2_budget_rollup.py
Exit 0 iff parent_budget == leaf_total == the sum of the parent's DIRECT child rollup
rows, AND the naive sum over all ledger rows (leaves + rollups) would double count,
proving the ledger's roll-up view is derived, never added twice. Uses a 3-level chain
so the nested double-count trap (deep + deep.leaf) is exercised for real.
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
mid = Workflow(id="mid", nodes=(Subworkflow(id="leaf", workflow_ref="shared-body"),))
parent = Workflow(
    id="parent",
    nodes=(
        Subworkflow(id="sibA", workflow_ref="shared-body", id_namespace="sibA"),
        Subworkflow(id="sibB", workflow_ref="shared-body", id_namespace="sibB"),
        Subworkflow(id="deep", workflow_ref="mid", id_namespace="deep"),
    ),
)

with tempfile.TemporaryDirectory() as td:
    res = execute(parent, {"shared-body": shared, "mid": mid}, td)
    a = res.rollup_assertion()
    rows = res.ledger.as_rows()
    top_level = [r for r in rows if r["kind"] == "rollup" and r["parent_id"] is None]
    ok = (
        res.parent_budget == 15
        and res.ledger.leaf_total() == 15
        and sum(r["amount"] for r in top_level) == 15
        and a["exact"] is True
        and a["top_level_rollup_matches"] is True
        and a["top_level_child_sum"] == 15
        # nested chain recorded both levels, and naive accounting WOULD double count
        and a["child_sum"] == 20  # naive all-levels child sum over-counts the chain
        and a["naive_would_double_count"] is True
        and a["naive_including_rollups"] == 35  # 15 leaves + 20 rollup rows
    )

out = {
    "probe": "probe2-budget-rollup-exact",
    "unit_id": "IMP-0217",
    "parent_budget": res.parent_budget,
    "child_budgets": res.child_budgets,
    "top_level_rollups": top_level,
    "rollup_assertion": a,
    "ledger_rows": rows,
    "pass": ok,
}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-rollup.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0217-probe2 rollup assertion did not hold")
    raise SystemExit(1)
print("SUCCESS:IMP-0217-probe2 parent budget == leaf total == direct-child rollups; naive sum double counts")
