"""End-to-end tests for BP-INC-03 (card 69), orphaned-run recovery by deterministic join.

Mechanism under test: no model judgement participates in the reconstruction. The join is keyed on
agentId, a deliberately-wrong `key` join is run as a control and MUST be worse, the ledger is
tri-state, and the three counts must reconcile against a declared denominator before any agent is
allowed to read anything.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "orphaned-run-recovery-from-disk"


@pytest.fixture(scope="module")
def doc() -> dict:
    return H.load(NAME)


def test_schema_and_semantics_are_clean(doc: dict) -> None:
    assert H.conformance_failures(doc) == []


def test_inline_units_pass_normative_and_strict(doc: dict) -> None:
    assert H.inline_units(doc)
    assert H.unit_profile_failures(doc, "normative") == []
    assert H.unit_profile_failures(doc, "strict") == []


def test_sentinels_name_their_own_units(doc: dict) -> None:
    assert H.sentinel_violations(doc) == []


def test_worked_example_conforms(doc: dict) -> None:
    assert H.worked_example_failures(doc) == []


def test_worked_example_checker_fires_on_a_dropped_binding(doc: dict) -> None:
    fails = H.worked_example_failures(H.mutated(doc, H.drop_a_required_binding))
    assert any("has no value in the worked example" in f for f in fails), fails


def test_worked_example_checker_fires_on_a_wrong_typed_value(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["params"]["dispatched_agent_count"] = "one thousand"

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("example value is str" in f for f in fails), fails


# ---------------------------------------------- mechanism: a declared denominator exists at all


def test_the_denominator_is_a_required_param(doc: dict) -> None:
    spec = doc["params"]["dispatched_agent_count"]
    assert spec["required"] is True
    assert spec["type"] == "integer"
    assert "DENOMINATOR" in spec["description"]
    assert "default" not in spec, (
        "a defaulted denominator would let a recovery invent its own completeness measure"
    )


def test_the_accounting_gate_compares_a_computed_total_to_the_denominator(doc: dict) -> None:
    expr = H.gate_expressions(doc)["accounting-closes"]
    assert "accounted_agents == dispatched_agent_count" in expr
    assert "unaccounted_agents == 0" in expr
    # the sum itself is computed by the unit, because the expression grammar has no arithmetic
    unit = H.stage(doc, "emit-tri-state-ledger")["work_unit"]
    assert "sum exactly to dispatched_agent_count" in unit["question_or_target"]
    assert "accounting-does-not-close" in unit["failure_classification"]


def test_an_arithmetic_expression_would_not_parse_and_is_therefore_not_used(doc: dict) -> None:
    """Documents the measured constraint: the grammar has no `+`, so a gate cannot compute a sum."""

    def bend(d: dict) -> None:
        d["gates"]["accounting-closes"]["expression"] = (
            "recovered + recovered_partial + lost == dispatched_agent_count"
        )

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-007" in v and "'+'" in v for v in violations), violations


# --------------------------------------------- mechanism: the wrong-key control must be worse


def test_the_wrong_key_control_is_run_and_required_to_lose(doc: dict) -> None:
    assert doc["params"]["run_wrong_key_control"]["default"] is True
    st = H.stage(doc, "wrong-key-control")
    assert st["when"] == "run_wrong_key_control == true"
    expr = H.gate_expressions(doc)["wrong-key-control-failed-as-expected"]
    assert expr == "wrong_key_complete_rows < agentid_complete_rows"
    unit = st["work_unit"]
    assert "content hash rather than a label" in unit["question_or_target"]
    assert "control-inverted" in unit["failure_classification"]
    tests = " ".join(unit["tests_required"])
    assert "the recovery must halt" in tests, (
        "an inverted control means the premise or the join is wrong; proceeding would be silent"
    )


def test_the_control_gate_runs_before_the_ledger_is_trusted(doc: dict) -> None:
    order = H.top_level_stage_ids(doc)
    assert order.index("wrong-key-control") < order.index("control-gate")
    assert order.index("control-gate") < order.index("emit-tri-state-ledger")
    assert H.stage(doc, "emit-tri-state-ledger")["depends_on"] == ["control-gate"]


def test_deleting_the_control_gate_is_detected(doc: dict) -> None:
    def bend(d: dict) -> None:
        del d["gates"]["wrong-key-control-failed-as-expected"]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-005" in v for v in violations), violations


# ---------------------------------------------------- mechanism: tri-state, not binary


def test_the_ledger_is_tri_state_and_partial_may_not_collapse(doc: dict) -> None:
    expr = H.gate_expressions(doc)["tri-state-is-not-binary"]
    assert "marked_recovered == 0" in expr
    assert "marked_lost == 0" in expr, (
        "collapsing partial into EITHER neighbour must fail, so both directions are asserted"
    )
    unit = H.stage(doc, "emit-tri-state-ledger")["work_unit"]
    tests = " ".join(unit["tests_required"])
    assert "asserted against both wrong answers" in tests
    assert "partial-collapsed" in unit["failure_classification"]


def test_dropping_one_direction_of_the_tri_state_check_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["tri-state-is-not-binary"]["expression"] = (
            "rows_with_transcript_but_no_artifact_marked_recovered == 0"
        )

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == []
    assert "marked_lost" not in H.gate_expressions(mutant)["tri-state-is-not-binary"]


# -------------------------------------- mechanism: agents read only after the arithmetic closes


def test_the_only_judgement_stage_runs_last_and_depends_on_both_gates(doc: dict) -> None:
    order = H.top_level_stage_ids(doc)
    assert order[-1] == "summarise-recovered-work"
    assert order.index("accounting-gate") < order.index("tri-state-gate")
    assert H.stage(doc, "summarise-recovered-work")["depends_on"] == ["tri-state-gate"]
    join_role = doc["roles"]["join-runner"]
    assert "Deterministic code only" in join_role["description"]
    assert "forbidden from inferring a mapping" in join_role["description"]


def test_the_recovery_is_read_only_over_the_session_root(doc: dict) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    assert "platform/**" in policy["forbid_write_paths"]
    assert "command-center/WORK-UNIT-CATALOG.json" in policy["forbid_write_paths"]
    writes = [t for t in H.all_tool_tokens(doc) if t.startswith("Write(")]
    assert writes and all(t.startswith("Write(command-center/recovery/") for t in writes), writes


def test_absent_journals_are_a_runtime_finding_not_zero_work(doc: dict) -> None:
    unit = H.stage(doc, "locate-run")["work_unit"]
    assert "finding about the RUNTIME, not about the work" in unit["question_or_target"]
    assert "walk-too-narrow" in unit["failure_classification"]
    tests = " ".join(unit["tests_required"])
    assert "widest plausible root" in tests, "a depth-limited walk under-counts the denominator"
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["runtime-left-nothing-to-recover"]["expression"] == "journals_found == 0"
    assert rules["runtime-left-nothing-to-recover"]["on_stop"] == "emit-partial"


def test_replay_is_fully_deterministic_because_the_inputs_are_on_disk(doc: dict) -> None:
    replay = doc["replay"]
    assert replay["deterministic"] is True
    assert replay["verify"] == "hash-equal"
    assert replay["on_divergence"] == "fail"
    assert "filesystem-order" in replay["forbid_nondeterministic_sources"]
