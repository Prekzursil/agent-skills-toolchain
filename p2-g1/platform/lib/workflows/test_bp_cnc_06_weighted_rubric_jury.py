"""FLAGSHIP end-to-end test: bp-cnc-06 Weighted Rubric Jury with Critical-Error Override.

Mechanism pinned here:

  1. The rubric is FROZEN AND HASHED before the artifact is read, and the freeze gate blocks
     with on_fail == "fail". A rubric changed after seeing the artifact is a justification.
  2. Deterministic metrics are computed BEFORE any scoring call - never ask a model for a number
     you can measure (an exact algorithm measured 86% versus judgement, with 100% of the errors
     pointing at data loss).
  3. ONE CALL PER DIMENSION, expressed as a fan-out with max_concurrency == 1 so the calls are
     genuinely serialised rather than nominally sequential.
  4. UNKNOWN is EXCLUDED from the composite and stated - never defaulted to mid-scale.
  5. A critical dimension at zero CAPS the composite. The cap gate blocks.
  6. Cross-vendor reconciliation is CONSERVATIVE (minimum, never mean), because a mean
     reintroduces exactly the averaging the override exists to prevent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

BP = "bp-cnc-06-weighted-rubric-jury"


def test_end_to_end_all_layers_clean() -> None:
    failures = C.all_layer_failures(C.load(BP))
    assert not any(failures.values()), {k: v for k, v in failures.items() if v}


def test_is_declared_flagship() -> None:
    assert C.load(BP)["flagship"] is True


# ---------------------------------------------------------- mechanism 1: the rubric freeze


def test_the_rubric_freeze_gate_blocks_and_is_the_first_stage() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["rubric-frozen-before-read"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert "artifact_bytes_read_at_freeze == 0" in gate["expression"]
    assert "weights_changed_after_freeze == 0" in gate["expression"]
    assert doc["stages"][0]["id"] == "freeze-rubric"
    assert doc["stages"][1]["id"] == "freeze-gate"
    wu = C.find_stage(doc, "freeze-rubric")["work_unit"]
    assert wu["retry_policy"].startswith("no retry after the artifact has been read")


def test_the_rubric_param_is_an_inline_schema_that_is_itself_valid() -> None:
    """DSL-SEM-010 validates the escape-hatch schema; check the shape it actually enforces."""
    doc = C.load(BP)
    schema = doc["params"]["rubric"]["schema"]
    assert schema["required"] == ["dimensions", "scale"]
    dim = schema["properties"]["dimensions"]["items"]
    assert dim["required"] == ["name", "weight", "critical"], (
        "a dimension with no critical flag cannot participate in the override"
    )
    assert schema["properties"]["scale"]["const"] == "0-4", (
        "the canonical scale is 9-dim 0-4; the legacy 0-10 scale is retired"
    )
    _, advisories = C.semantic(doc)
    assert not advisories


def test_mutation_control_an_invalid_inline_rubric_schema_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["params"]["rubric"]["schema"].__setitem__("type", 7),
        "semantic",
        what="corrupt the inline rubric schema so it is no longer a valid JSON Schema "
        "(DSL-SEM-010)",
    )


# ------------------------------------------------- mechanism 2: deterministic metrics first


def test_deterministic_metrics_are_computed_before_any_scoring_call() -> None:
    doc = C.load(BP)
    stages = [s["id"] for s in doc["stages"]]
    assert stages.index("deterministic-metrics") < stages.index("score")
    wu = C.find_stage(doc, "deterministic-metrics")["work_unit"]
    assert "86%" in wu["assigned_model_vendor_role"]["basis"], (
        "the reason for computing rather than judging is a measurement, and it is cited"
    )
    assert "NOT-COMPUTED" in wu["evidence_requirement"], (
        "a metric that could not be computed must be recorded, never estimated"
    )


# ----------------------------------------------- mechanism 3: one call per dimension exactly


def test_the_scoring_fanout_is_serialised_to_one_call_per_dimension() -> None:
    score = C.find_stage(C.load(BP), "score")
    assert score["kind"] == "fanout"
    assert score["max_concurrency"] == 1, (
        "the reliability protocol is ONE call per dimension; any concurrency above 1 lets two "
        "dimensions be scored in one context and reintroduces the drift the protocol removes"
    )
    assert score["over"]["source"] == "artifact"
    assert score["over"]["ref"].endswith("rubric-freeze.json"), (
        "the fan-out iterates the FROZEN rubric, not the caller's param, so a post-freeze edit "
        "cannot change what gets scored"
    )


def test_it_is_the_only_bp2_blueprint_with_a_serialised_fanout() -> None:
    serialised = []
    for bid in C.BP2_IDS:
        for shape in C.fingerprint(C.load(bid))["fanout_shape"]:
            if ":mc=1:" in shape:
                serialised.append(bid)
    assert serialised == [BP], serialised


def test_mutation_control_parallelising_the_dimension_scoring_is_visible() -> None:
    doc = C.load(BP)
    C.find_stage(doc, "score")["max_concurrency"] = 9
    assert C.fingerprint_key(doc) != C.fingerprint_key(C.load(BP)), (
        "max_concurrency is part of the fanout_shape fingerprint, so parallelising the protocol "
        "is a structural change and cannot pass as the same workflow"
    )
    failures = C.all_layer_failures(doc)
    assert not any(failures.values()), (
        "documented LIMIT: the schema cannot know that THIS fan-out must stay serialised, so "
        "the constraint lives in this test. If a future rule catches it, tighten rather than "
        f"delete: { {k: v[:2] for k, v in failures.items() if v} }"
    )


# --------------------------------------------------- mechanism 4: UNKNOWN excluded, not defaulted


def test_unknown_dimensions_are_excluded_and_stated() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["unknown-excluded-not-defaulted"]
    assert gate["blocking"] is True
    assert "dimensions_defaulted_to_midscale == 0" in gate["expression"]
    assert "unknown_dimensions_excluded_and_stated == true" in gate["expression"]
    assert "scores_without_evidence == 0" in gate["expression"]
    assert "midscale-default" in doc["retry_policy"]["no_retry_on"], (
        "a mid-scale default must not be reachable by retrying"
    )
    wu = C.find_stage(doc, "score-one-dimension")["work_unit"]
    assert any("never 2 of 4" in t for t in wu["tests_required"])


def test_the_barrier_rejects_a_hedged_score_string() -> None:
    barrier = C.find_stage(C.load(BP), "score")["barrier"]
    assert "roughly a 2" in barrier["reject_result_matching"], (
        "a hedged score is not a score; the fan-in gate names the shape it refuses"
    )


# --------------------------------------------------- mechanism 5: the critical-error override


def test_a_critical_zero_must_cap_the_composite() -> None:
    doc = C.load(BP)
    gate = doc["gates"]["critical-override-applied"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert (
        gate["expression"]
        == "critical_zero_present == false OR composite_capped == true"
    ), (
        "the implication form matters: it permits an uncapped composite ONLY when no critical "
        "dimension scored zero"
    )
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["capped-by-critical-error"]["expression"] == "composite_capped == true"
    wu = C.find_stage(doc, "composite")["work_unit"]
    assert any("MUST be capped, not averaged" in t for t in wu["tests_required"])
    assert "recomputable by hand" in wu["evidence_requirement"]


def test_the_stability_gate_is_advisory_while_the_cap_gate_blocks() -> None:
    """Both kinds coexist on purpose: score drift is advisory, a fatal flaw is not."""
    doc = C.load(BP)
    assert doc["gates"]["protocol-is-stabilising"]["blocking"] is False
    assert doc["gates"]["protocol-is-stabilising"]["on_fail"] == "record-and-continue"
    assert doc["gates"]["critical-override-applied"]["blocking"] is True
    blocking = {
        name: g["blocking"] for name, g in doc["gates"].items() if isinstance(g, dict)
    }
    assert sum(1 for v in blocking.values() if v is False) == 1, blocking


def test_mutation_control_inverting_the_override_expression_is_visible() -> None:
    doc = C.load(BP)
    doc["gates"]["critical-override-applied"]["expression"] = (
        "composite_capped == false"
    )
    assert C.fingerprint_key(doc) == C.fingerprint_key(C.load(BP)), (
        "the fingerprint keys on gate PREDICATE and blocking/on_fail, not on expression text, "
        "so an inverted expression is NOT structurally visible - which is exactly why this "
        "assertion on the expression string exists as a separate test above"
    )
    assert not any(C.all_layer_failures(doc).values()), (
        "and it stays schema-valid, confirming the expression semantics are only protected here"
    )


# ------------------------------------------------ mechanism 6: conservative reconciliation


def test_cross_vendor_reconciliation_takes_the_lower_score_not_the_mean() -> None:
    doc = C.load(BP)
    stage = C.find_stage(doc, "cross-vendor-critique")
    assert stage["when"] == "cross_vendor_critic == true"
    assert doc["roles"]["codex-critic"]["vendor"] == "openai"
    assert doc["roles"]["codex-critic"]["cross_vendor_required"] is True
    wu = stage["work_unit"]
    assert "taking the LOWER score" in wu["question_or_target"]
    assert any("never the mean" in t for t in wu["tests_required"])
    assert "reconciliation-not-conservative" in wu["failure_classification"]


# ------------------------------------------------------------------------ worked examples


def test_worked_examples_cover_the_cap_and_the_unknown_exclusion() -> None:
    doc = C.load(BP)
    assert not C.worked_example_errors(doc)
    pos, neg = C.worked_examples(doc)
    assert pos["arm"] == "positive"
    assert "composite_capped == true" in pos["expected_terminal_state"]
    weights = [d["weight"] for d in pos["params"]["rubric"]["dimensions"]]
    assert abs(sum(weights) - 1.0) < 1e-9, f"positive-arm weights sum to {sum(weights)}"
    assert any(d["critical"] for d in pos["params"]["rubric"]["dimensions"])
    assert neg["arm"] == "negative-control"
    assert "UNKNOWN" in neg["expected_terminal_state"]
    assert "30%-weighted invented number" in neg["walkthrough"]


def test_the_owner_decision_is_surfaced_at_every_invocation() -> None:
    doc = C.load(BP)
    assert doc["params"]["artifact_class"]["required"] is True, (
        "the open owner decision is WHICH classes get a canonical rubric; making artifact_class "
        "required surfaces that question on every run instead of defaulting past it"
    )
    assert "OPEN" in doc["x_extensions"]["owner_decision"]
