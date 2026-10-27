"""End-to-end test for FLAGSHIP blueprint BP-TST-07 (card 60),
tst.hook-event-reachability-conformance.

Mechanism protected: the test MUST FAIL on the current tree (two implemented handlers are
unreachable); an UNDECLARED handler is a finding rather than a pass; and the WIRE-or-RETIRE
decision belongs to the owner, because the test can only report.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

SLUG = "tst.hook-event-reachability-conformance"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_the_both_states_control_requires_a_failure_on_the_current_tree() -> None:
    """The sharpest form of the rule: a conformance test that is GREEN on a tree with two
    known-unreachable handlers is silent in both states, so it measures nothing."""
    d = doc()
    gate = d["gates"]["both-states-control"]
    assert gate["on_fail"] == "fail" and gate["blocking"] is True
    assert kit.evaluate_gate(d, "both-states-control") is True
    assert (
        kit.evaluate_gate(
            d,
            "both-states-control",
            {
                "fails_on_known_unreachable_handlers": False,
                "known_unreachable_count": 0,
            },
        )
        is False
    )
    assert (
        kit.evaluate_gate(d, "both-states-control", {"known_unreachable_count": 1})
        is False
    ), "the card names TWO live cases; a control that accepts one is half-blind"


def test_a_detector_that_is_blind_escalates_rather_than_reporting_a_pass() -> None:
    d = doc()
    rule = next(r for r in d["stopping_rules"] if r["id"] == "detector-is-blind")
    assert rule["on_stop"] == "escalate"
    ctx = kit.worked_context(d)
    assert _expr.evaluate(rule["expression"], ctx, strict=True) is False
    assert (
        _expr.evaluate(
            rule["expression"],
            {**ctx, "fails_on_known_unreachable_handlers": False},
            strict=True,
        )
        is True
    ), "a blind detector must trigger the escalation path"


def test_an_undeclared_handler_is_a_finding_not_a_pass() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "undeclared-not-assumed-fine") is True
    assert (
        kit.evaluate_gate(
            d,
            "undeclared-not-assumed-fine",
            {"handlers_without_declared_event_treated_as_pass": 1},
        )
        is False
    )


def test_registration_shape_is_checked_and_not_only_event_names() -> None:
    """The existing manifest gate validates keys and JSON round-tripping but NOT matcher nesting."""
    d = doc()
    assert kit.evaluate_gate(d, "shape-validated") is True
    assert (
        kit.evaluate_gate(d, "shape-validated", {"matcher_groups_checked": False})
        is False
    )
    assert (
        kit.evaluate_gate(
            d, "shape-validated", {"command_handler_fields_checked": False}
        )
        is False
    )


def test_the_membership_assertion_is_an_exact_set_difference_not_a_heuristic() -> None:
    d = doc()
    unit = next(
        u
        for s in d["stages"]
        if s["id"] == "assert-membership"
        for u in [s["work_unit"]]
    )
    assert "set difference" in unit["question_or_target"]
    assert "not a heuristic" in unit["question_or_target"]
    assert unit["retry_policy"].startswith("no retry"), (
        "a set difference does not become different on a second run"
    )
    assert "recomputable from the artifact" in unit["evidence_requirement"]
    stage = next(s for s in d["stages"] if s["id"] == "assert-membership")
    assert stage["retry"]["strategy"] == "none"


def test_the_wire_or_retire_decision_belongs_to_the_owner() -> None:
    d = doc()
    stage = next(s for s in d["stages"] if s["id"] == "owner-wire-or-retire")
    assert stage["kind"] == "human_checkpoint"
    assert stage["approval_mode"] == "owner-only"
    assert stage["on_timeout"] == "escalate", (
        "an unanswered wiring decision must not silently proceed"
    )
    assert "wire-all" in stage["options"] and "retire-all" in stage["options"]
    assert "defer-with-recorded-risk" in stage["options"], (
        "leaving a security guard under a non-existent event is not a neutral option"
    )
    ctx = kit.worked_context(d)
    assert _expr.evaluate(stage["when"], ctx, strict=True) is True
    assert (
        _expr.evaluate(
            stage["when"], {**ctx, "unreachable_handler_count": 0}, strict=True
        )
        is False
    )


def test_it_cannot_write_to_the_hook_tree_it_is_auditing() -> None:
    """A conformance test that can edit its subject can make itself pass."""
    d = doc()
    assert "hooks/**" in d["tool_policy"]["forbid_write_paths"]
    assert ".claude/**" in d["tool_policy"]["forbid_write_paths"]
    assert "Write" in d["tool_policy"]["deny"] and "Edit" in d["tool_policy"]["deny"]
    assert d["tool_policy"]["network"] == "none"


def test_the_measured_basis_is_direct_not_projected() -> None:
    d = doc()
    x = d["x_extensions"]
    assert "NOT event names" in x["measured_basis"]
    assert x["owner_decision"], "the card marks this OWNER-DECISION: YES"
    assert d["retry_policy"]["strategy"] == "none", (
        "a deterministic set check does not retry"
    )


def test_MUTATION_weakening_the_both_states_control_removes_its_power() -> None:
    d = doc()
    bad = {"fails_on_known_unreachable_handlers": False, "known_unreachable_count": 0}
    assert kit.evaluate_gate(d, "both-states-control", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["both-states-control"]["expression"] = (
        "events_tuple_parsed == true"
    )
    ctx = kit.worked_context(weakened)
    ctx.update(bad)
    assert (
        _expr.evaluate(
            weakened["gates"]["both-states-control"]["expression"], ctx, strict=True
        )
        is True
    ), (
        "with the control weakened to a parse check, a blind detector now passes - which is "
        "exactly the state the real expression rejects"
    )


def test_MUTATION_dropping_the_both_states_control_is_rejected() -> None:
    kit.assert_rejected(
        kit.drop_stage(doc(), "both-states-control"), "both-states control removed"
    )


def test_MUTATION_dropping_the_membership_gate_is_rejected() -> None:
    kit.assert_rejected(
        kit.drop_stage(doc(), "membership-asserted"), "membership gate removed"
    )
