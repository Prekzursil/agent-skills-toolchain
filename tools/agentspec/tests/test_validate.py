"""Spec validation: one negative case per violation id, plus a clause-coverage test.

The clause-coverage test is the anti-divergence guard the SSOT structure depends on: every
declared violation id MUST be produced by at least one negative case here, so a validator
clause cannot exist without a test that exercises it.
"""

from __future__ import annotations

import dataclasses

import pytest

from agentspec import SPEC_VERSION
from agentspec.spec import Barrier, FanOut, Pipeline, ReceiptSpec, Workflow, WorkUnit
from agentspec.validate import VIOLATIONS, validate_workflow


def _receipt(fmt: str = "json") -> ReceiptSpec:
    if fmt == "json":
        return ReceiptSpec(fmt="json", required_fields=("status",))
    return ReceiptSpec(fmt="text", forbidden_markers=("in progress",))


def _unit(uid: str = "u1", **kw: object) -> WorkUnit:
    base: dict[str, object] = {
        "id": uid,
        "prompt": "do the thing",
        "timeout_s": 1800,
        "receipt": _receipt(),
    }
    base.update(kw)
    return WorkUnit(**base)  # type: ignore[arg-type]


def _wf(**kw: object) -> Workflow:
    base: dict[str, object] = {
        "id": "wf",
        "spec_version": SPEC_VERSION,
        "units": (_unit("u1"), _unit("u2", depends_on=("u1",))),
        "nodes": (
            FanOut(id="f1", units=("u1", "u2")),
            Barrier(id="b1", awaits=("f1",)),
            Pipeline(id="p1", stages=("u1", "u2")),
        ),
        "budget_micro": 100,
    }
    base.update(kw)
    return Workflow(**base)  # type: ignore[arg-type]


def test_a_well_formed_workflow_has_no_violations() -> None:
    assert validate_workflow(_wf()) == ()


def test_a_text_receipt_with_forbidden_markers_is_accepted() -> None:
    wf = _wf(units=(_unit("u1", receipt=_receipt("text")),), nodes=())
    assert validate_workflow(wf) == ()


# --- one negative case per violation id ---------------------------------------------------

CASES: dict[str, Workflow] = {
    "spec-version-unsupported": _wf(spec_version="99"),
    "workflow-id-empty": _wf(id="  "),
    "workflow-no-units": _wf(units=(), nodes=()),
    "unit-id-empty": _wf(units=(_unit(""),), nodes=()),
    "unit-id-duplicate": _wf(units=(_unit("u1"), _unit("u1")), nodes=()),
    "unit-prompt-empty": _wf(units=(_unit("u1", prompt="   "),), nodes=()),
    "unit-timeout-missing": _wf(units=(_unit("u1", timeout_s=0),), nodes=()),
    "unit-budget-negative": _wf(units=(_unit("u1", budget_micro=-1),), nodes=()),
    "unit-dep-unknown": _wf(units=(_unit("u1", depends_on=("ghost",)),), nodes=()),
    "unit-dep-self": _wf(units=(_unit("u1", depends_on=("u1",)),), nodes=()),
    "unit-dep-cycle": _wf(
        units=(_unit("u1", depends_on=("u2",)), _unit("u2", depends_on=("u1",))),
        nodes=(),
    ),
    "unit-worktree-no-writes": _wf(
        units=(_unit("u1", isolation="worktree"),), nodes=()
    ),
    "unit-isolation-unknown": _wf(units=(_unit("u1", isolation="chroot"),), nodes=()),
    "unit-receipt-format-unknown": _wf(
        units=(_unit("u1", receipt=ReceiptSpec(fmt="yaml", required_fields=("a",))),),
        nodes=(),
    ),
    "unit-receipt-clause-vacuous": _wf(
        units=(_unit("u1", receipt=ReceiptSpec(fmt="json")),), nodes=()
    ),
    "node-id-empty": _wf(nodes=(FanOut(id=" ", units=("u1",)),)),
    "node-id-duplicate": _wf(
        nodes=(FanOut(id="n", units=("u1",)), Barrier(id="n", awaits=("u1",)))
    ),
    "node-id-collides-unit": _wf(nodes=(FanOut(id="u1", units=("u1",)),)),
    "fanout-empty": _wf(nodes=(FanOut(id="f1", units=()),)),
    "fanout-unit-unknown": _wf(nodes=(FanOut(id="f1", units=("ghost",)),)),
    "fanout-unit-duplicate": _wf(nodes=(FanOut(id="f1", units=("u1", "u1")),)),
    "barrier-empty": _wf(nodes=(Barrier(id="b1", awaits=()),)),
    "barrier-awaits-unknown": _wf(nodes=(Barrier(id="b1", awaits=("ghost",)),)),
    "barrier-policy-unknown": _wf(
        nodes=(Barrier(id="b1", awaits=("u1",), policy="most"),)
    ),
    "pipeline-too-short": _wf(nodes=(Pipeline(id="p1", stages=("u1",)),)),
    "pipeline-stage-unknown": _wf(nodes=(Pipeline(id="p1", stages=("u1", "ghost")),)),
    "budget-total-negative": _wf(budget_micro=-1),
    "budget-units-exceed-total": _wf(
        units=(_unit("u1", budget_micro=60), _unit("u2", budget_micro=60)),
        nodes=(),
        budget_micro=100,
    ),
}


@pytest.mark.parametrize("code", sorted(CASES))
def test_each_violation_id_is_produced_by_its_negative_case(code: str) -> None:
    assert code in validate_workflow(CASES[code])


def test_every_declared_violation_has_a_negative_case() -> None:
    """Clause coverage: no validator clause may exist without a test that exercises it."""
    assert sorted(VIOLATIONS) == sorted(CASES)


def test_violations_are_returned_sorted_and_deduplicated() -> None:
    wf = _wf(id=" ", spec_version="99", units=(), nodes=())
    result = validate_workflow(wf)
    assert result == tuple(sorted(set(result)))
    assert result == (
        "spec-version-unsupported",
        "workflow-id-empty",
        "workflow-no-units",
    )


def test_a_three_unit_cycle_is_detected() -> None:
    wf = _wf(
        units=(
            _unit("a", depends_on=("c",)),
            _unit("b", depends_on=("a",)),
            _unit("c", depends_on=("b",)),
        ),
        nodes=(),
    )
    assert "unit-dep-cycle" in validate_workflow(wf)


def test_a_diamond_dependency_is_not_a_cycle() -> None:
    """Detector control: the cycle finder must be silent on a legal DAG with a re-join."""
    wf = _wf(
        units=(
            _unit("a"),
            _unit("b", depends_on=("a",)),
            _unit("c", depends_on=("a",)),
            _unit("d", depends_on=("b", "c")),
        ),
        nodes=(),
    )
    assert validate_workflow(wf) == ()


def test_a_text_receipt_with_no_forbidden_markers_is_also_vacuous() -> None:
    """Both receipt formats must supply a content clause, or the AND-gate's 4th clause is
    vacuous and a rail that exits 0 over a "still in progress" body reads as SUCCESS."""
    wf = _wf(units=(_unit("u1", receipt=ReceiptSpec(fmt="text")),), nodes=())
    assert "unit-receipt-clause-vacuous" in validate_workflow(wf)


def test_a_worktree_unit_declaring_writes_is_accepted() -> None:
    """The measured scar: file-disjoint agents share one git index and `git add -A`
    sweeps siblings, so a worktree unit MUST declare the paths it writes."""
    wf = _wf(units=(_unit("u1", isolation="worktree", writes=("tools/x/",)),), nodes=())
    assert validate_workflow(wf) == ()


def test_a_unit_budget_equal_to_the_total_is_accepted() -> None:
    """Boundary: <= total is legal, > total is not."""
    wf = _wf(units=(_unit("u1", budget_micro=100),), nodes=(), budget_micro=100)
    assert validate_workflow(wf) == ()


def test_replace_keeps_the_record_valid() -> None:
    """dataclasses.replace is the only supported mutation path (frozen records)."""
    unit = dataclasses.replace(_unit("u1"), timeout_s=60)
    assert unit.timeout_s == 60
    assert validate_workflow(_wf(units=(unit,), nodes=())) == ()
