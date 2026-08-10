"""End-to-end tests for BP-DAT-01 (card 72), deterministic-differ-first classification.

Mechanism under test: a ROUTING decision (algorithm versus judgement) followed by a TWO-ARM
comparison scored on error DIRECTION rather than accuracy. The agent arm is run deliberately, on
the same labelled items, blind to the algorithm's answer, and a run whose errors all point at data
loss is disqualified no matter how accurate it is.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "deterministic-differ-first-classification"


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


def test_worked_example_binds_every_declared_param_it_uses(doc: dict) -> None:
    ex = doc["x_extensions"]["worked_example"]
    assert set(ex["params"]) <= set(doc["params"])
    assert "diverged" in ex["params"]["verdict_vocabulary"]
    assert set(ex["params"]["dangerous_verdicts"]) <= set(
        ex["params"]["verdict_vocabulary"]
    ), "a dangerous verdict outside the vocabulary could never be counted"


# ------------------------------------------------------------ mechanism: routing, both ways


def test_stage_zero_may_answer_JUDGEMENT_and_that_is_a_legal_outcome(doc: dict) -> None:
    unit = H.stage(doc, "exactness-triage")["work_unit"]
    assert "ALGORITHMIC or JUDGEMENT" in unit["question_or_target"]
    assert "legitimate answer" in unit["question_or_target"]
    tests = " ".join(unit["tests_required"])
    assert "must be classified ALGORITHMIC" in tests
    assert "must be classified JUDGEMENT" in tests
    assert "must not force an algorithm onto everything" in tests
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["question-is-judgement-not-algorithm"]["expression"] == (
        "question_is_algorithmically_decidable == false"
    )
    assert rules["question-is-judgement-not-algorithm"]["on_stop"] == "emit-partial"


def test_the_algorithm_stage_is_conditional_on_the_routing_verdict(doc: dict) -> None:
    st = H.stage(doc, "write-the-algorithm")
    assert st["when"] == "question_is_algorithmically_decidable == true"
    order = H.top_level_stage_ids(doc)
    assert order[0] == "exactness-triage"
    assert order.index("write-the-algorithm") < order.index("run-over-full-set")


# --------------------------------------- mechanism: validate on a sample before the full set


def test_the_algorithm_is_validated_against_human_labels_first(doc: dict) -> None:
    assert doc["params"]["hand_checked_sample"]["required"] is True
    assert (
        H.gate_expressions(doc)["algorithm-agrees-with-hand-checked-sample"]
        == "algorithm_disagreements_with_sample == 0"
    )
    order = H.top_level_stage_ids(doc)
    assert order.index("sample-validation-gate") < order.index("run-over-full-set")
    unit = H.stage(doc, "write-the-algorithm")["work_unit"]
    assert (
        "falling back to agents is explicitly not the remedy"
        in unit["question_or_target"]
    )
    assert "never pivot to agent classification" in unit["retry_policy"]
    tests = " ".join(unit["tests_required"])
    assert "one-directional check must be shown to miss it" in tests
    assert "deliberately broken algorithm must disagree" in tests, (
        "a validation that cannot fail is not a validation"
    )


def test_the_full_set_is_covered_with_an_explicit_skipped_list(doc: dict) -> None:
    expr = H.gate_expressions(doc)["full-set-covered"]
    assert "items_classified == items_in_dataset" in expr
    assert "items_skipped == 0" in expr
    unit = H.stage(doc, "run-over-full-set")["work_unit"]
    assert "never an implicit pass" in unit["question_or_target"]
    tests = " ".join(unit["tests_required"])
    assert "depth-limited walk under-counts" in tests
    assert "closed-set control" in tests


# ------------------------------------- mechanism: two arms, and the second one is blind


def test_the_agent_arm_is_independent_and_uses_the_strongest_model(doc: dict) -> None:
    unit = H.stage(doc, "agent-classify-one")["work_unit"]
    assert "WITHOUT receiving the algorithm's verdict" in unit["question_or_target"]
    assert "was NOT supplied" in unit["evidence_requirement"]
    assert "arm-not-independent" in unit["failure_classification"]
    tests = " ".join(unit["tests_required"])
    assert "independence control" in tests
    basis = unit["assigned_model_vendor_role"]["basis"]
    assert "strongest available model" in basis, (
        "a weak control arm would understate agent capability and flatter the algorithm"
    )
    assert doc["model_routing"]["forbid_downgrade_below"] == "opus"


def test_the_two_arms_classify_the_same_labelled_items(doc: dict) -> None:
    fan = H.stage(doc, "run-agent-control-arm")
    assert fan["over"]["source"] == "artifact"
    assert fan["over"]["ref"].endswith("#/labelled_subset")
    assert fan["depends_on"] == ["coverage-gate"], (
        "the arm must run after the algorithm has classified the full set, on its labelled subset"
    )
    assert doc["params"]["agent_arm_size"]["minimum"] >= 5


# --------------------------------------- mechanism: DIRECTION is the metric, not accuracy


def test_the_direction_gate_is_the_blocking_verdict(doc: dict) -> None:
    assert H.gate_expressions(doc)["no-dangerous-direction-error"] == (
        "dangerous_direction_errors == 0"
    )
    assert (
        doc["gates"]["no-dangerous-direction-error"]["on_fail"] == "escalate-to-human"
    )
    unit = H.stage(doc, "measure-error-direction")["work_unit"]
    target = unit["question_or_target"]
    assert "DANGEROUS" in target and "OVER-CAUTIOUS" in target
    assert "make the dangerous count the headline" in target
    ev = unit["evidence_requirement"]
    assert "accuracy may be reported but never as the headline" in ev
    assert "accuracy-reported-as-headline" in unit["failure_classification"]
    tests = " ".join(unit["tests_required"])
    assert "must be counted DANGEROUS" in tests
    assert "headline is accuracy rather than direction must fail review" in tests


def test_the_dangerous_verdict_set_is_a_required_input(doc: dict) -> None:
    spec = doc["params"]["dangerous_verdicts"]
    assert spec["required"] is True
    assert spec["min_items"] >= 1, (
        "without a declared dangerous set, direction cannot be computed at all"
    )
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["agent-arm-points-at-data-loss"]["expression"] == (
        "dangerous_direction_errors >= 1"
    )
    assert rules["agent-arm-points-at-data-loss"]["on_stop"] == "escalate"


def test_weakening_the_direction_gate_to_a_ratio_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["no-dangerous-direction-error"]["expression"] = "accuracy >= 0.85"

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == [], (
        "still schema-valid; the loss is the mechanism"
    )
    assert (
        "dangerous_direction_errors"
        not in H.gate_expressions(mutant)["no-dangerous-direction-error"]
    )


# -------------------------------------- mechanism: agents only on genuinely judgement residue


def test_the_residue_is_agent_only_and_must_contain_nothing_mechanical(
    doc: dict,
) -> None:
    fan = H.stage(doc, "judge-residue")
    assert fan["over"]["ref"].endswith("#/residue_requiring_judgement")
    assert fan["depends_on"] == ["direction-gate"]
    assert H.stage(doc, "judge-one-residue-item")["role"] == "residue-judge"
    assert H.gate_expressions(doc)["residue-is-genuinely-judgement"] == (
        "residue_items_mechanically_decidable == 0"
    )
    assert H.top_level_stage_ids(doc)[-1] == "residue-purity-gate"


def test_the_estimate_names_the_measurement_it_claims_to_come_from(doc: dict) -> None:
    est = doc["estimate"]
    assert est["basis"] == "historical-measured"
    src = est["measurement_source"]
    for token in ("338", "86%", "31", "fan-out-contract"):
        assert token in src, token


def test_claiming_a_measured_basis_without_naming_the_measurement_is_rejected(
    doc: dict,
) -> None:
    def bend(d: dict) -> None:
        del d["estimate"]["measurement_source"]

    errs = H.schema_errors(H.mutated(doc, bend))
    assert any("measurement_source" in e for e in errs), errs
