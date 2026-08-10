"""End-to-end test for BP-REQ-03 (EVPI-Gated Clarification).

Executes the blueprint's own worked example through mechanisms.evpi_questions, using the cap and
window thresholds READ OUT OF the shipped document, so mutating the document changes the test.
"""

from __future__ import annotations

import mechanisms as m
from bp3_testkit import (
    assert_contract_valid,
    both_states_control,
    declared_stopping_rule,
    gate_expressions,
    load_blueprint,
    stage,
    stage_ids,
    worked_example,
)

BP = "bp-req-03.evpi-gated-clarification"


def doc():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(doc())


def test_declared_stage_graph_matches_the_design_card():
    d = doc()
    assert stage_ids(d) == ["s0-scan", "s1-identify", "s2-evpi", "s2b-window", "s3-ask"]
    # S3 ASK is a human checkpoint, which is what makes this blueprint's actuator the OWNER
    assert stage(d, "s3-ask")["kind"] == "human_checkpoint"
    assert stage(d, "s3-ask")["approval_mode"] == "owner-only"
    # the window gate must run BEFORE the owner is ever asked
    assert stage(d, "s3-ask")["depends_on"] == ["s2b-window"]


def _cap(d) -> int:
    return int(d["params"]["max_questions"]["maximum"])


def test_the_cap_is_three_and_the_gate_expression_says_so():
    d = doc()
    assert _cap(d) == 3
    assert "questions_asked <= 3" in gate_expressions(d)["evpi-positive"]
    assert "actions_elapsed <= 2" in gate_expressions(d)["window-open"]
    assert "bypass_star == false" in gate_expressions(d)["window-open"]


def _run_example(d, *, star=None, elapsed=None):
    ex = worked_example(d)
    cands = [
        m.Question(text=c["text"], options=c["options"])
        for c in ex["input"]["candidates"]
    ]
    return m.evpi_questions(
        cands,
        star_prefixed=ex["input"]["star_prefixed"] if star is None else star,
        actions_elapsed=ex["input"]["actions_elapsed"] if elapsed is None else elapsed,
        max_questions=_cap(d),
    )


def test_worked_example_drops_the_zero_evpi_question():
    d = doc()
    ex = worked_example(d)
    kept = _run_example(d)
    assert [k.text for k in kept] == ex["expected"]["kept_texts"]
    assert len(ex["input"]["candidates"]) - len(kept) == ex["expected"]["dropped_count"]


def test_declared_controls_hold_star_bypass_and_closed_window():
    d = doc()
    controls = {c["why"]: c for c in worked_example(d)["controls"]}
    assert len(controls) == 2
    assert _run_example(d, star=True) == []
    assert _run_example(d, elapsed=3) == []
    # and the window is genuinely open at the boundary, so the rule is a window and not a ban
    assert len(_run_example(d, elapsed=2)) == 1


def test_stopping_rule_has_a_minimum_condition_so_it_cannot_fire_cheaply():
    rule = declared_stopping_rule(doc(), "no-material-ambiguity-or-cap-reached")
    assert rule["minimum_conditions"] == "repo_context_scanned == true"


def test_clarification_is_never_cached_or_resumed():
    """A half-asked question set must be re-derived against the CURRENT prompt."""
    d = doc()
    assert d["cache"]["enabled"] is False
    assert d["resume"]["enabled"] is False


def test_dry_run_forbids_actually_asking_the_owner():
    assert "AskUserQuestion" in doc()["dry_run"]["forbid_tools"]


# ------------------------------------------------------------------- both-states controls


def _invariant_window_gate_precedes_the_ask(d):
    assert stage(d, "s3-ask")["depends_on"] == ["s2b-window"]
    assert "actions_elapsed <= 2" in gate_expressions(d)["window-open"]


def test_mutation_control_removing_the_window_gate_breaks_the_invariant():
    both_states_control(
        doc(),
        _invariant_window_gate_precedes_the_ask,
        lambda x: x["gates"]["window-open"].__setitem__("expression", "true_always"),
        "window gate no longer bounds the pre-execution window",
    )


def _invariant_cap_is_three(d):
    assert _cap(d) == 3
    assert len(_run_example(d, star=False, elapsed=0)) <= 3


def test_mutation_control_raising_the_cap_breaks_the_invariant():
    both_states_control(
        doc(),
        _invariant_cap_is_three,
        lambda x: x["params"]["max_questions"].__setitem__("maximum", 9),
        "question cap raised above three",
    )
