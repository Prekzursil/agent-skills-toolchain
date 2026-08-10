"""FLAGSHIP end-to-end test: bp-cnc-01 Schema-Typed Five-Persona Design Council.

The mechanism this blueprint exists to enforce, and therefore what these tests pin:

  1. FIVE FIXED PERSONAS, parallel and BLIND (independence == "independent" on every one).
  2. An ENUMERATED verdict vocabulary - free text is a schema failure, not a soft pass. The
     enumeration gate is BLOCKING.
  3. Retry-ONCE-then-null-lens per persona (measured: our own schemas reject our own agents
     22.7% of the time), so a schema-invalid verdict never silently disappears.
  4. Null-lens accounting that must RECONCILE - a null lens is NOT-CHECKED, never an approval.
  5. SHADOW posture on the design verdict: the aggregate gate is NON-blocking, so this council
     can never wedge the owner. The distinction between the blocking schema contract and the
     non-blocking design verdict is deliberate and is asserted here.

Every mechanism test is paired with a BOTH-STATES mutation control, so a green run proves the
detector discriminates rather than that it is silent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

BP = "bp-cnc-01-five-persona-design-council"


def _stage(doc: dict, stage_id: str) -> dict:
    from wfdsl import semantics as S

    for _, st in S.iter_stages(doc):
        if st.get("id") == stage_id:
            return st
    raise AssertionError(f"stage {stage_id!r} not found in {BP}")


# ------------------------------------------------------------------ end-to-end conformance


def test_end_to_end_all_layers_clean() -> None:
    failures = C.all_layer_failures(C.load(BP))
    assert not any(failures.values()), {k: v for k, v in failures.items() if v}


def test_is_declared_flagship() -> None:
    assert C.load(BP)["flagship"] is True
    assert BP in C.FLAGSHIP_IDS


# ------------------------------------------------------------------------ mechanism 1: five


def test_five_personas_fan_out_in_parallel_and_blind() -> None:
    doc = C.load(BP)
    review = _stage(doc, "review")
    assert review["kind"] == "fanout"
    assert review["over"]["source"] == "param"
    assert review["over"]["ref"] == "personas"
    assert review["max_concurrency"] >= 5, "five personas must be able to run at once"

    default_personas = doc["params"]["personas"]["default"]
    assert default_personas == ["pm", "architect", "designer", "security", "cto"]
    for name in default_personas:
        assert doc["roles"][name]["independence"] == "independent", (
            f"persona {name} is not blind; blindness is the mechanism, not a nicety"
        )


def test_the_security_persona_reasons_and_has_no_elevated_access() -> None:
    doc = C.load(BP)
    security = doc["roles"]["security"]
    assert security["authority"] == "veto"
    assert "Bash" not in security["tool_permissions"]
    assert doc["tool_policy"]["network"] == "none"
    assert "Bash" in doc["tool_policy"]["deny"]


# ------------------------------------------------------ mechanism 2: enumerated verdicts


def test_the_enumeration_gate_is_blocking() -> None:
    gate = C.load(BP)["gates"]["verdicts-are-enumerated"]
    assert gate["blocking"] is True, (
        "a free-text verdict makes the fan-in unreadable; that is a contract failure, not a "
        "design opinion, so this gate blocks even though the design verdict does not"
    )
    assert "free_text_verdicts == 0" in gate["expression"]
    assert "blocking_findings_without_section_anchor == 0" in gate["expression"]


def test_mutation_control_undeclared_stage_role_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "persona-verdict").__setitem__("role", "not-a-declared-role"),
        "semantic",
        what="point the persona stage at a role that is not in the roles block (DSL-SEM-004)",
    )


def test_removing_a_persona_role_is_NOT_caught_by_the_schema_and_that_is_documented() -> None:
    """Documented LIMIT, verified rather than assumed.

    The five personas are dispatched as fan-out ITEMS (``over.ref == "personas"``), not via a
    per-stage ``role`` field, so DSL-SEM-004 cannot see a deleted persona role. Deleting one
    leaves the document valid. The pairing between the persona enum and the roles block is
    therefore enforced HERE, and this test states that plainly instead of leaving a silent gap.
    """
    doc = C.load(BP)
    doc["roles"].pop("security")
    failures = C.all_layer_failures(doc)
    assert not any(failures.values()), (
        "if a future rule DOES catch this, tighten the assertion rather than deleting it: "
        f"{ {k: v[:2] for k, v in failures.items() if v} }"
    )
    good = C.load(BP)
    persona_enum = set(good["params"]["personas"]["items"]["enum"])
    assert persona_enum <= set(good["roles"]), (
        "every persona in the enum must have a declared role - the check the DSL cannot make"
    )


# -------------------------------------------------- mechanism 3: retry once then null lens


def test_each_persona_retries_exactly_once_then_records_a_null_lens() -> None:
    body = _stage(C.load(BP), "persona-verdict")
    retry = body["retry"]
    assert retry["max_attempts"] == 2, (
        "exactly one retry: the design card says restate the vocabulary inline once, then record "
        "a null lens - grinding a third time hides a systematic schema mismatch"
    )
    assert "schema-invalid" in retry["retry_on"]
    assert "artifact-missing" in retry["no_retry_on"]
    wu = body["work_unit"]
    assert "null-lens" in wu["failure_classification"]
    assert "22.7%" in wu["retry_policy"], "the measured rejection rate is the reason for the rule"


def test_mutation_control_unbounded_persona_retry_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: C.find_stage(d, "persona-verdict")["retry"].pop("max_attempts"),
        "schema",
        what="remove the retry bound so a schema-invalid persona could be retried forever",
    )


# ------------------------------------------------ mechanism 4: null lenses never approve


def test_null_lens_accounting_must_reconcile_and_uses_no_arithmetic_in_the_expression() -> None:
    doc = C.load(BP)
    rule = next(r for r in doc["stopping_rules"] if r["id"] == "all-personas-terminal")
    assert rule["expression"] == "unaccounted_personas == 0 AND reconciliation_ok == true"
    assert "+" not in rule["expression"], (
        "the wfdsl expression grammar has NO arithmetic operators - a '+' here is a DSL-SEM-007 "
        "violation, so the runner computes the difference and the DSL asserts on the result"
    )
    wu = _stage(doc, "aggregate")["work_unit"]
    assert "unaccounted_personas == 0" in wu["completion_sentinel"]
    assert any("null lens must never increment the approval count" in t for t in wu["tests_required"])


def test_mutation_control_arithmetic_in_an_expression_is_caught() -> None:
    """The grammar limitation is real, so prove the validator actually rejects arithmetic."""
    C.assert_mutation_caught(
        BP,
        lambda d: d["stopping_rules"][0].__setitem__(
            "expression", "verdicts_returned + null_lenses == personas_requested"
        ),
        "semantic",
        what="use an arithmetic operator the DSL expression grammar cannot parse",
    )


# ------------------------------------------------------------- mechanism 5: SHADOW posture


def test_the_design_verdict_gate_is_non_blocking_shadow() -> None:
    doc = C.load(BP)
    shadow = doc["gates"]["shadow-aggregate"]
    assert shadow["blocking"] is False
    assert shadow["on_fail"] == "record-and-continue"
    terminal = _stage(doc, "shadow-gate")
    assert terminal["kind"] == "gate"
    assert terminal["gate_ref"] == "shadow-aggregate", (
        "the LAST stage must be the non-blocking one; if a blocking gate came last the council "
        "could wedge the owner, which the SHADOW posture forbids"
    )
    assert doc["stages"][-1]["id"] == "shadow-gate"


def test_mutation_control_promoting_the_shadow_gate_to_blocking_is_visible() -> None:
    """This one is a DOCUMENTED LIMIT, not a caught mutation.

    Flipping ``blocking`` to true keeps the document schema-valid and semantically clean - the
    DSL has no rule that a named gate must stay advisory, and inventing one would be wrong
    because most gates SHOULD block. So the SHADOW posture is protected by this test, not by
    the schema. Stated explicitly rather than left as a silent gap.
    """
    doc = C.load(BP)
    doc["gates"]["shadow-aggregate"]["blocking"] = True
    failures = C.all_layer_failures(doc)
    assert not any(failures.values()), (
        "if a future schema DOES reject this, tighten the assertion instead of deleting it: "
        f"{ {k: v[:2] for k, v in failures.items() if v} }"
    )
    assert C.fingerprint_key(doc) != C.fingerprint_key(C.load(BP)), (
        "the structural fingerprint MUST notice a blocking-flag flip, otherwise the distinctness "
        "proof would treat a shadow council and a blocking council as the same workflow"
    )


# ---------------------------------------------------------------- worked examples are real


def test_both_worked_example_arms_are_present_and_typed() -> None:
    doc = C.load(BP)
    assert not C.worked_example_errors(doc)
    arms = [e["arm"] for e in C.worked_examples(doc)]
    assert arms == ["positive", "negative-control"], arms


def test_the_positive_arm_is_the_seeded_hole_benchmark() -> None:
    ex = C.worked_examples(C.load(BP))[0]
    assert "auth hole" in ex["name"]
    assert "blocking_findings == 1" in ex["expected_terminal_state"]
    assert ex["expected_gate_outcomes"]["shadow-aggregate"].startswith("RECORDED-NOT-BLOCKED")


def test_the_negative_arm_shows_a_null_lens_not_an_approval() -> None:
    ex = C.worked_examples(C.load(BP))[1]
    assert "null_lenses == 1" in ex["expected_terminal_state"]
    assert "does NOT increment the approval count" in ex["walkthrough"]


def test_mutation_control_a_worked_example_with_too_few_personas_is_caught() -> None:
    C.assert_mutation_caught(
        BP,
        lambda d: d["x_extensions"]["worked_examples"][0]["params"].__setitem__(
            "personas", ["pm", "architect"]
        ),
        "worked_examples",
        what="drop a worked example below the declared minimum of three personas",
    )
