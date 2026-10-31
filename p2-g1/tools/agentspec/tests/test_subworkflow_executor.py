"""IMP-0217: Subworkflow executor - id namespacing and budget roll-up.

Required signals (catalog):
  1. sibling subworkflows with identical internal ids do not collide
  2. budget roll-up exact, no double count
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from agentspec.subworkflow_executor import (
    ExecuteOpts,
    Subworkflow,
    Task,
    Workflow,
    execute,
)


def _colliding_fixture() -> tuple[Workflow, dict[str, Workflow]]:
    """Two sibling subworkflows referencing the SAME workflow_ref whose
    internal task id is IDENTICAL ("unit-a") - the collision fixture."""
    shared = Workflow(
        id="shared-body",
        nodes=(Task(id="unit-a", budget=3), Task(id="unit-b", budget=2)),
    )
    parent = Workflow(
        id="parent",
        nodes=(
            Subworkflow(
                id="sibA",
                workflow_ref="shared-body",
                id_namespace="sibA",
                param_bindings={"label": "from-A"},
            ),
            Subworkflow(
                id="sibB",
                workflow_ref="shared-body",
                id_namespace="sibB",
                param_bindings={"label": "from-B"},
            ),
        ),
    )
    return parent, {"shared-body": shared}


def test_sibling_subworkflows_with_identical_internal_ids_do_not_collide() -> None:
    parent, registry = _colliding_fixture()
    with tempfile.TemporaryDirectory() as td:
        res = execute(parent, registry, td, params={"label": "root"})
        receipt_ids = sorted(res.receipts)
        # both internal ids exist under BOTH namespaces -> 2 receipts per task id
        a_receipts = [r for r in receipt_ids if r.endswith("::unit-a")]
        b_receipts = [r for r in receipt_ids if r.endswith("::unit-b")]
        assert len(a_receipts) == 2, f"unit-a must have 2 namespaced receipts, got {a_receipts}"
        assert len(b_receipts) == 2, f"unit-b must have 2 namespaced receipts, got {b_receipts}"
        assert set(a_receipts) == {"sibA::unit-a", "sibB::unit-a"}
        assert set(b_receipts) == {"sibB::unit-b", "sibA::unit-b"}
        # artifact spaces are isolated per namespace
        assert set(res.artifact_spaces) == {"sibA", "sibB"}
        sibA_dir = Path(res.artifact_spaces["sibA"])
        sibB_dir = Path(res.artifact_spaces["sibB"])
        assert sibA_dir != sibB_dir and sibA_dir.is_dir() and sibB_dir.is_dir()
        # the two same-id artifacts are distinct files with distinct payloads
        fa = Path(res.artifacts["sibA::unit-a"]).read_text(encoding="utf-8")
        fb = Path(res.artifacts["sibB::unit-a"]).read_text(encoding="utf-8")
        assert fa == "from-A" and fb == "from-B", "payloads must not leak across siblings"


def test_budget_rollup_exact_no_double_count() -> None:
    parent, registry = _colliding_fixture()
    with tempfile.TemporaryDirectory() as td:
        res = execute(parent, registry, td)
    assertion = res.rollup_assertion()
    # parent budget == sum of child budgets (leaf amounts, no rollup double count)
    assert res.parent_budget == 10, f"parent budget must be 10, got {res.parent_budget}"
    assert assertion["rollup_matches"] is True
    assert assertion["exact"] is True
    # the naive sum including rollup rows WOULD double count; ledger does not
    assert assertion["naive_would_double_count"] is True
    assert assertion["naive_including_rollups"] == 20
    assert assertion["leaf_total"] == 10
    assert assertion["child_sum"] == 10
    # ledger leaf view equals the parent budget exactly
    assert res.ledger.leaf_total() == res.parent_budget


def test_shared_single_namespace_off_switch_keeps_legacy_flat_ids() -> None:
    """The namespacing=False escape hatch still executes without collision-crash,
    and the ledger still reconciles (leaf-only accounting)."""
    parent, registry = _colliding_fixture()
    with tempfile.TemporaryDirectory() as td:
        res = execute(parent, registry, td, opts=ExecuteOpts(namespacing=False))
    assert res.ledger.leaf_total() == res.parent_budget == 10
    assert "sibA" in res.child_budgets and "sibB" in res.child_budgets

