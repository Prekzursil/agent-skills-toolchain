"""The SPEC types are frozen records and the SINGLE SOURCE OF TRUTH for any runtime."""

from __future__ import annotations

import dataclasses

import pytest

from agentspec import SPEC_VERSION
from agentspec.spec import (
    BARRIER_POLICIES,
    ISOLATIONS,
    RECEIPT_FORMATS,
    Barrier,
    FanOut,
    Pipeline,
    ReceiptSpec,
    Workflow,
    WorkUnit,
    unit_ids,
)


def _unit(uid: str = "u1", **kw: object) -> WorkUnit:
    base: dict[str, object] = {
        "id": uid,
        "prompt": "do the thing",
        "timeout_s": 1800,
        "receipt": ReceiptSpec(fmt="json", required_fields=("status",)),
    }
    base.update(kw)
    return WorkUnit(**base)  # type: ignore[arg-type]


def test_spec_version_is_pinned() -> None:
    assert SPEC_VERSION == "1"


def test_closed_vocabularies() -> None:
    assert RECEIPT_FORMATS == ("json", "text")
    assert BARRIER_POLICIES == ("all", "any")
    assert ISOLATIONS == ("shared", "worktree")


def test_work_unit_defaults_are_conservative() -> None:
    unit = _unit()
    assert unit.depends_on == ()
    assert unit.budget_micro == 0
    assert unit.isolation == "shared"
    assert unit.writes == ()


def test_work_unit_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _unit().timeout_s = 1  # type: ignore[misc]


def test_receipt_spec_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ReceiptSpec(fmt="text").fmt = "json"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("spec", "vacuous"),
    [
        (ReceiptSpec(fmt="json"), True),
        (ReceiptSpec(fmt="json", required_fields=("status",)), False),
        (ReceiptSpec(fmt="text"), True),
        (ReceiptSpec(fmt="text", forbidden_markers=("in progress",)), False),
        # An unknown fmt is NOT reported vacuous: both call sites check the format first and
        # emit their own format error, so answering True here would mask it with a second id.
        (ReceiptSpec(fmt="yaml"), False),
        # A json spec is not rescued by text-only fields, or vice versa — the clause that
        # matters is the one the AND-gate will actually evaluate for that format.
        (ReceiptSpec(fmt="json", forbidden_markers=("in progress",)), True),
        (ReceiptSpec(fmt="text", required_fields=("status",)), True),
    ],
    ids=[
        "json-bare",
        "json-with-fields",
        "text-bare",
        "text-with-markers",
        "unknown-fmt",
        "json-with-only-markers",
        "text-with-only-fields",
    ],
)
def test_is_vacuous_is_the_ONE_predicate_both_call_sites_share(
    spec: ReceiptSpec, vacuous: bool
) -> None:
    """A vacuous spec reduces the six-clause AND-gate to "exit 0 AND non-empty".

    ``validate_workflow`` reported it as ``unit-receipt-clause-vacuous`` while ``judge`` — the
    function a consumer calls DIRECTLY, without ever building a Workflow — accepted it. One
    predicate, two call sites, so the two cannot drift apart.
    """
    assert spec.is_vacuous() is vacuous


def test_barrier_defaults_to_all_and_null_tolerant() -> None:
    """A barrier must tolerate a null unit result — a died agent must not deadlock it."""
    barrier = Barrier(id="b1", awaits=("u1",))
    assert barrier.policy == "all"
    assert barrier.null_tolerant is True


def test_fanout_and_pipeline_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        FanOut(id="f1", units=("u1",)).units = ()  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Pipeline(id="p1", stages=("u1", "u2")).stages = ()  # type: ignore[misc]


def test_workflow_is_frozen_and_holds_its_nodes() -> None:
    wf = Workflow(
        id="wf",
        spec_version=SPEC_VERSION,
        units=(_unit("u1"), _unit("u2")),
        nodes=(FanOut(id="f1", units=("u1", "u2")),),
        budget_micro=10,
    )
    assert unit_ids(wf) == ("u1", "u2")
    with pytest.raises(dataclasses.FrozenInstanceError):
        wf.budget_micro = 0  # type: ignore[misc]


def test_unit_ids_preserves_declaration_order() -> None:
    wf = Workflow(
        id="wf",
        spec_version=SPEC_VERSION,
        units=(_unit("z"), _unit("a")),
        nodes=(),
        budget_micro=0,
    )
    assert unit_ids(wf) == ("z", "a")


def test_unit_by_id_returns_the_declared_unit() -> None:
    from agentspec.spec import unit_by_id

    wf = Workflow(
        id="wf",
        spec_version=SPEC_VERSION,
        units=(_unit("a"), _unit("b")),
        nodes=(),
        budget_micro=0,
    )
    assert unit_by_id(wf, "b").id == "b"


def test_unit_by_id_raises_on_an_unknown_id() -> None:
    from agentspec.spec import unit_by_id

    wf = Workflow(
        id="wf",
        spec_version=SPEC_VERSION,
        units=(_unit("a"),),
        nodes=(),
        budget_micro=0,
    )
    with pytest.raises(KeyError, match="nope"):
        unit_by_id(wf, "nope")


def test_node_ids_covers_all_three_node_kinds() -> None:
    from agentspec.spec import node_ids

    wf = Workflow(
        id="wf",
        spec_version=SPEC_VERSION,
        units=(_unit("u1"), _unit("u2")),
        nodes=(
            FanOut(id="f1", units=("u1", "u2")),
            Barrier(id="b1", awaits=("f1",)),
            Pipeline(id="p1", stages=("u1", "u2")),
        ),
        budget_micro=0,
    )
    assert node_ids(wf) == ("f1", "b1", "p1")
