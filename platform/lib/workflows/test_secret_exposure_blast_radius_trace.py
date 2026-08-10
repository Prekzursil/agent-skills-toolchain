"""End-to-end tests for BP-SEC-02 (card 62), the secret-exposure blast-radius trace.

Mechanism under test: ONE value traced across MANY surface classes in parallel, with UNSEARCHED
as a first-class verdict that may never be folded into CLEAN, a rotation step the workflow refuses
to perform itself, and a guard-gap repair loop whose verify arm is independent of its repair arm.

The hardest constraint is negative - the credential VALUE must never reach an artifact - so the
tests assert on the policy and the declared evidence rather than on prose promises.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "secret-exposure-blast-radius-trace"


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


# ------------------------------------------------- mechanism: a secret param forces redaction


def test_a_secret_param_is_declared_and_forces_export_redaction(doc: dict) -> None:
    handle = doc["params"]["secret_handle"]
    assert handle["type"] == "secret_ref"
    assert handle["secret"] is True
    assert "default" not in handle, "a secret_ref can never carry a literal default"
    assert doc["portability"]["export"]["redact_secrets"] is True


def test_turning_off_export_redaction_with_a_secret_param_is_caught(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["portability"]["export"]["redact_secrets"] = False

    mutant = H.mutated(doc, bend)
    # the schema pins redact_secrets to const true, AND DSL-SEM-013 exists as the semantic twin
    assert H.schema_errors(mutant) != [] or any(
        "DSL-SEM-013" in v for v in H.semantic_violations(mutant)
    )


def test_a_secret_ref_param_with_a_default_is_rejected(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["params"]["secret_handle"]["default"] = "literal-token-value"

    errs = H.schema_errors(H.mutated(doc, bend))
    assert errs != [], "a secret_ref carrying a default must not validate"


# --------------------------------------------- mechanism: UNSEARCHED is not CLEAN (denominator)


def test_the_trace_declares_a_denominator_before_it_searches(doc: dict) -> None:
    order = H.top_level_stage_ids(doc)
    assert order.index("enumerate-surfaces") < order.index("search-surfaces")
    assert H.stage(doc, "search-surfaces")["depends_on"] == ["enumerate-surfaces"]
    expr = H.gate_expressions(doc)["unsearched-is-not-clean"]
    assert "surfaces_recorded == surfaces_requested" in expr
    assert "surfaces_silently_dropped == 0" in expr


def test_the_fanout_is_over_a_declared_param_and_survives_stragglers(doc: dict) -> None:
    fan = H.stage(doc, "search-surfaces")
    assert fan["over"]["source"] == "param"
    assert fan["over"]["ref"] in doc["params"]
    assert fan["max_concurrency"] >= 2
    assert fan["on_item_failure"] == "continue", (
        "one unsearchable surface must not abort the trace - it must be recorded"
    )
    assert fan["barrier"]["on_partial"] == "proceed-with-quarantine"
    assert fan["barrier"]["verify_artifact_exists"] is True


def test_a_fanout_over_an_undeclared_param_is_caught(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "search-surfaces":
                s["over"]["ref"] = "surfaces_that_do_not_exist"

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-012" in v for v in violations), violations


# --------------------------------------------------- mechanism: rotation is the owner's action


def test_rotation_is_an_owner_checkpoint_not_a_task(doc: dict) -> None:
    cp = H.stage(doc, "owner-rotation-decision")
    assert cp["kind"] == "human_checkpoint"
    assert cp["approval_mode"] == "owner-only"
    assert cp["on_timeout"] == "escalate"
    assert set(cp["options"]) == {
        "rotated",
        "rotation-scheduled",
        "accepting-exposure-with-reason",
    }
    owner = doc["roles"]["owner"]
    assert owner["vendor"] == "human" and owner["authority"] == "owner"
    # no stage may hold a tool that could rotate a credential
    tokens = H.all_tool_tokens(doc)
    for banned in ("Bash", "Bash:curl", "Bash:gh", "WebFetch"):
        assert banned not in tokens, (
            f"{banned} would put rotation inside the workflow's reach"
        )
    assert doc["tool_policy"]["network"] == "none"


def test_the_hard_constraint_is_recorded_in_the_document_itself(doc: dict) -> None:
    text = doc["x_extensions"]["hard_constraint"]
    for phrase in ("never rotates", "owner"):
        assert phrase in text, text


# ------------------------------------ mechanism: guard-gap repair with an INDEPENDENT verify


def test_guard_gap_repair_loop_has_a_separate_verify_arm(doc: dict) -> None:
    loop = H.stage(doc, "close-guard-gap")
    assert loop["kind"] == "repair_loop"
    assert loop["target"] == ["analyse-guard-gap"]
    assert loop["require_root_cause"] is True
    assert 1 <= loop["max_attempts"] <= 10
    diag, rep, ver = loop["diagnose"], loop["repair"], loop["verify"]
    assert {diag["id"], rep["id"], ver["id"]} == {
        "diagnose-guard",
        "repair-guard",
        "verify-guard-fires",
    }
    assert ver["kind"] == "gate", (
        "a repair loop without an independent verify is a retry"
    )
    expr = ver["gate"]["expression"]
    assert "guard_fires_on_exposing_input == true" in expr
    assert "guard_silent_on_benign_twin == true" in expr, (
        "the verify must assert BOTH states, or a guard that always fires would pass"
    )


def test_a_repair_loop_targeting_a_missing_stage_is_caught(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "close-guard-gap":
                s["target"] = ["no-such-stage"]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-009" in v for v in violations), violations


def test_dropping_the_verify_arm_is_rejected_by_the_schema(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "close-guard-gap":
                del s["verify"]

    errs = H.schema_errors(H.mutated(doc, bend))
    assert any("verify" in e for e in errs), errs
