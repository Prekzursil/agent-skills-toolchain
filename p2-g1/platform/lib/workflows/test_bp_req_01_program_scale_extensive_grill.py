"""FLAGSHIP end-to-end test: bp-req-01 Program-Scale Extensive Grill.

Mechanism pinned here:

  1. RECALL RUNS FIRST. No owner attention is spent before the ledger and memory are searched -
     the dominant measured failure is re-asking a question a note already answers.
  2. FOUNDATIONAL BEFORE DETAIL, enforced through dependency EDGES so the ordering is checkable
     rather than a matter of taste, and EVERY question carries a recommendation - a bare question
     is a process violation.
  3. ONE QUESTION AT A TIME: a bounded loop whose body IS a human checkpoint followed by an
     immediate durable write. This is the only bp-2 blueprint with a human checkpoint inside a
     loop.
  4. OWNER ATTENTION is the scarce resource: the loop stops when the remaining questions are all
     lower-consequence than the modelled ask cost, and it PARKS rather than guessing.
  5. It is the only bp-2 blueprint that delegates to a CHILD WORKFLOW (constraint inversion),
     and that delegation is conditional and non-fatal.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

BP = "bp-req-01-program-scale-extensive-grill"


def test_end_to_end_all_layers_clean() -> None:
    failures = C.all_layer_failures(C.load(BP))
    assert not any(failures.values()), {k: v for k, v in failures.items() if v}


def test_is_declared_flagship() -> None:
    assert C.load(BP)["flagship"] is True


# ------------------------------------------------------------------- mechanism 1: recall first


def test_recall_runs_before_any_owner_question() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["recall-ran-first"]
    assert gate["blocking"] is True
    assert "recall_executed == true" in gate["expression"]
    assert "questions_already_answered_in_ledger == 0" in gate["expression"]
    stages = [s["id"] for s in doc["stages"]]
    assert stages.index("scout") == 0
    assert stages.index("recall-gate") < stages.index("ask-loop")
    assert (
        "mcp__basic-memory__search_notes" in doc["roles"]["scout"]["tool_permissions"]
    )
    assert "mcp__basic-memory__search_notes" in doc["tool_policy"]["allow"], (
        "DSL-SEM-011 is deny-by-default: a role tool that is not in the allow list is a violation"
    )


def test_mutation_control_a_role_tool_outside_the_allow_list_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["tool_policy"]["allow"].remove("mcp__basic-memory__search_notes"),
        "semantic",
        what="request a tool the deny-by-default policy does not allow (DSL-SEM-011)",
    )


# ------------------------------------------------- mechanism 2: foundational-first, never bare


def test_ordering_and_recommendations_are_gated_together() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["foundational-before-detail"]
    assert gate["blocking"] is True
    assert "detail_questions_before_foundational == 0" in gate["expression"]
    assert "every_question_has_a_recommendation == true" in gate["expression"]
    wu = C.find_stage(doc, "structure")["work_unit"]
    assert (
        "which OTHER questions its answer would change" in wu["evidence_requirement"]
    ), "the dependency EDGE is what makes foundational-first mechanically checkable"
    assert "bare-question" in doc["failure_policy"]["classify_as"]
    assert any("FIRST, not tenth" in t for t in wu["tests_required"])
    assert any("both-states control" in t for t in wu["tests_required"]), (
        "the ordering check must carry its own both-states arm, or a green run proves nothing"
    )


def test_the_orderer_is_routed_to_maximum_effort() -> None:
    doc = C.load(BP)
    assert doc["roles"]["question-orderer"]["effort"] == "max"
    route = next(
        r for r in doc["model_routing"]["routes"] if "question_orderer" in r["when"]
    )
    assert route["target"]["effort"] == "max"
    assert doc["model_routing"]["forbid_downgrade_below"] == "opus"


# ------------------------------------------- mechanism 3: one question at a time, durably


def test_the_ask_loop_body_is_a_human_checkpoint_followed_by_a_durable_write() -> None:
    doc = C.load(BP)
    loop = C.find_stage(doc, "ask-loop")
    assert loop["kind"] == "loop"
    body = loop["body"]
    assert [b["id"] for b in body] == ["ask-one", "record-answer"]
    assert body[0]["kind"] == "human_checkpoint"
    assert body[1]["depends_on"] == ["ask-one"], (
        "the write must be sequenced AFTER the answer, or the loop can advance on an unwritten one"
    )
    assert body[1]["checkpoint"] is True
    assert body[0]["approval_mode"] == "owner-only"
    assert body[0]["on_timeout"] == "escalate"
    assert isinstance(body[0]["timeout_seconds"], int)
    assert "park-this-question" in body[0]["options"]


def test_it_is_the_only_bp2_blueprint_with_a_human_checkpoint_inside_a_loop() -> None:
    hits = []
    for bid in C.BP2_IDS:
        for shape in C.fingerprint(C.load(bid))["loop_shape"]:
            if "human_checkpoint" in shape:
                hits.append(bid)
    assert sorted(set(hits)) == sorted(
        {BP, "bp-req-02-recursive-decision-ledger-walk"}
    ), hits
    # both have one, so distinguish on the SECOND body member
    mine = C.find_stage(C.load(BP), "ask-loop")["body"]
    theirs = C.find_stage(C.load("bp-req-02-recursive-decision-ledger-walk"), "walk")[
        "body"
    ]
    assert len(mine) == 2 and len(theirs) == 3, (
        "req-01 asks then records (flat list); req-02 asks, expands the tree, then checkpoints - "
        "the extra expansion stage is the mechanical difference between a flat grill and a "
        "dependent-tree walk"
    )


def test_the_loop_is_bounded_and_has_an_anti_grind_exit() -> None:
    conv = C.find_stage(C.load(BP), "ask-loop")["convergence"]
    assert conv["max_iterations"] == 200
    assert conv["no_progress_rounds"] == 3
    assert conv["on_no_convergence"] == "emit-partial"
    assert conv["converged_when"] == (
        "open_decisions == 0 OR remaining_consequence_below_ask_cost == true"
    )
    declared = {m["name"] for m in conv["metrics"]}
    assert {"open_decisions", "remaining_consequence_below_ask_cost"} <= declared, (
        "DSL-SEM-008 requires every convergence identifier to be a declared metric, a param or "
        "loop_var; an undeclared metric is a rule that can never fire"
    )


def test_mutation_control_an_undeclared_convergence_metric_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "ask-loop")["convergence"].__setitem__(
            "converged_when", "questions_feel_done == true"
        ),
        "semantic",
        what="converge on a metric that is declared nowhere (DSL-SEM-008)",
    )


def test_mutation_control_an_unbounded_loop_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "ask-loop")["convergence"].pop("max_iterations"),
        "schema",
        what="remove the iteration bound so the grill could spin forever",
    )


# ------------------------------------------------- mechanism 4: owner attention is the budget


def test_the_stopping_rules_price_owner_attention_and_park_rather_than_guess() -> None:
    doc = C.load(BP)
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["remaining-questions-not-worth-asking"]["expression"] == (
        "remaining_consequence_below_ask_cost == true"
    )
    assert rules["owner-unavailable-park-the-rest"]["on_stop"] == "emit-partial"
    assert doc["params"]["ask_cost_minutes"]["default"] == 4
    assert "OWNER ATTENTION" in doc["estimate"]["impact"]["blast_radius"]
    assert doc["estimate"]["wallclock_seconds"]["max"] == 86400, (
        "wallclock is dominated by the human checkpoint, not by compute; the estimate says so"
    )


def test_parked_questions_must_carry_a_consequence_rating() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["decision-log-is-authoritative"]
    assert "parked_questions_ordered_by_consequence == true" in gate["expression"]
    assert "decisions_without_rationale == 0" in gate["expression"]
    wu = C.find_stage(doc, "converge")["work_unit"]
    assert "next_stage plan" in wu["evidence_requirement"]
    assert "consequence-unrated" in wu["failure_classification"]


def test_a_choice_against_the_recommendation_must_be_recorded_as_such() -> None:
    wu = C.find_stage(C.load(BP), "record-answer")["work_unit"]
    assert "chose AGAINST the recommendation" in wu["evidence_requirement"]
    assert any(
        "not normalised to the recommendation" in t for t in wu["tests_required"]
    )
    assert "double-append" in wu["failure_classification"]


# ------------------------------------------------------------ mechanism 5: the child workflow


def test_the_conditional_child_workflow_resolves_and_is_non_fatal() -> None:
    doc = C.load(BP)
    stage = C.find_stage(doc, "invert-constraints")
    assert stage["kind"] == "subworkflow"
    assert stage["when"] == "invert_constraints_when_boxed_in == true"
    assert stage["propagate_failure"] is False, (
        "constraint inversion is an OPTIONAL aid; a failure there must not kill the grill"
    )
    assert stage["workflow"]["workflow_id"] in doc["subworkflows"], "DSL-SEM-006"
    declared = doc["subworkflows"]["bp-brn-03-constraint-inversion"]
    assert (
        declared["source"] == "platform/workflows/bp-brn-03-constraint-inversion.json"
    )
    assert (C.WF_DIR / "bp-brn-03-constraint-inversion.json").is_file(), (
        "the child workflow must exist on disk, not merely be named"
    )


def test_it_is_the_only_bp2_blueprint_with_a_subworkflow() -> None:
    with_sub = [
        bid for bid in C.BP2_IDS if C.fingerprint(C.load(bid))["has_subworkflow"]
    ]
    assert with_sub == [BP], with_sub


def test_mutation_control_an_unresolvable_subworkflow_reference_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "invert-constraints")["workflow"].__setitem__(
            "workflow_id", "bp-not-declared"
        ),
        "semantic",
        what="reference a subworkflow that is not in the subworkflows block (DSL-SEM-006)",
    )


# ------------------------------------------------------------------------ worked examples


def test_worked_examples_cover_the_hidden_foundational_choice_and_the_decline() -> None:
    doc = C.load(BP)
    assert not C.worked_example_errors(doc)
    pos, neg = C.worked_examples(doc)
    assert pos["arm"] == "positive"
    assert "next_stage == plan" in pos["expected_terminal_state"]
    assert (
        "asked FIRST" in pos["walkthrough"] or "orders it FIRST" in pos["walkthrough"]
    )
    assert neg["arm"] == "negative-control"
    assert "zero questions asked" in neg["expected_terminal_state"]
    assert "DECLINES to grill" in neg["walkthrough"], (
        "over-process on a well-scoped task is the second benchmark on the design card"
    )


def test_all_eight_grill_modes_are_carried_and_the_coverage_gap_is_disclosed() -> None:
    doc = C.load(BP)
    modes = doc["params"]["mode"]["enum"]
    assert len(modes) == 8
    assert set(modes) == set(doc["x_extensions"]["eight_grill_modes"])
    assert "UNVERIFIED whether all eight" in doc["params"]["mode"]["description"], (
        "the design card flags that mode coverage is unmeasured; the tag rides INLINE on the "
        "field it qualifies rather than sitting only in a trailing section"
    )
