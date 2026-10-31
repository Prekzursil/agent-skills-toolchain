"""IMP-0189 probe1: the two-level meta-workflow budget equals the sum of its
children, asserted against the immutable budget ledger (no double count: roll-up
rows are computed, never posted; the naive sum over all rows is the triple-count
a double-count would report).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.budget import Ledger  # noqa: E402
from agentspec.compose import (  # noqa: E402
    LeafUnit,
    MetaWorkflow,
    Subworkflow,
    rollup_budget,
)


def build_meta() -> MetaWorkflow:
    return MetaWorkflow(
        id="meta",
        budget_micro=45,
        children=(
            Subworkflow(
                id="embed-a",
                budget_micro=30,
                leaves=(LeafUnit("embed-a.u1", 10), LeafUnit("embed-a.u2", 20)),
            ),
            Subworkflow(
                id="embed-b",
                budget_micro=15,
                leaves=(LeafUnit("embed-b.u1", 15),),
            ),
        ),
    )


def main() -> int:
    checks = {}
    meta = build_meta()
    res = rollup_budget(meta, limit_micro=100)

    checks["parent_equals_child_sum"] = res.parent_total == res.child_sum == 45
    checks["child_sum_equals_leaf_total"] = res.child_sum == res.leaf_total == 45
    checks["ledger_spent_equals_parent"] = res.ledger_spent_micro == res.parent_total
    checks["naive_is_triple_count"] = res.naive_sum_all_rows == 135
    checks["no_double_count"] = (
        res.naive_sum_all_rows != res.parent_total and res.ok
    )

    amounts = [(e["kind"], e["node_id"], e["amount"]) for e in res.ledger_entries]
    expected_shapes = [
        ("leaf", "embed-a.u1", 10),
        ("leaf", "embed-a.u2", 20),
        ("rollup", "embed-a", 30),
        ("leaf", "embed-b.u1", 15),
        ("rollup", "embed-b", 15),
        ("rollup", "meta", 45),
    ]
    checks["ledger_entry_shapes"] = amounts == expected_shapes
    checks["rollup_children_declared"] = (
        res.ledger_entries[2]["children"] == ["embed-a.u1", "embed-a.u2"]
        and res.ledger_entries[5]["children"] == ["embed-a", "embed-b"]
    )

    # immutability: a replayed debit is refused, so a retry cannot double-post
    ledger = Ledger(limit_micro=100).debit("embed-a.u1", attempt=1, micro=10)
    refused = False
    try:
        ledger.debit("embed-a.u1", attempt=1, micro=10)
    except ValueError:
        refused = True
    checks["ledger_refuses_double_post"] = refused
    exhausted = False
    try:
        Ledger(limit_micro=44).debit("meta-child-sum", attempt=1, micro=45)
    except Exception:
        exhausted = True
    checks["ledger_enforces_ceiling"] = exhausted

    out = {
        "unit_id": "IMP-0189",
        "probe": "probe1-budget-rollup",
        "children": {c.id: c.budget_micro for c in meta.children},
        "parent_total": res.parent_total,
        "child_sum": res.child_sum,
        "leaf_total": res.leaf_total,
        "ledger_spent_micro": res.ledger_spent_micro,
        "naive_sum_all_rows": res.naive_sum_all_rows,
        "ledger_entries": res.ledger_entries,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0189-probe1 parent 45 == child sum 45 == leaf total 45 == ledger spend; naive row sum 135 is the rejected double-count; replayed debit refused")
        return 0
    print("FAILED:IMP-0189-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
