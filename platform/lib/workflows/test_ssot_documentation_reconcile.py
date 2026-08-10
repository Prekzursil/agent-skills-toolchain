"""End-to-end tests for blueprint 84, BP-DOC-03 ssot-documentation-reconcile (FLAGSHIP).

Three properties, three mutation controls:
  * AUTHORITY BY MEASURABILITY - the winning statement is the one a probe agrees with, and when no
    statement is measurable the fact is UNVERIFIED everywhere rather than one being blessed;
  * NO SILENT RESOLUTION - every rewritten statement lands in the superseded register; and
  * a FALSE-POSITIVE CONTROL - a sentence that legitimately repeats context is not rewritten,
    because a reconcile that flags legitimate repetition is vandalism.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp7_checks as C  # noqa: E402
import bp7_testkit as K  # noqa: E402
from wfdsl import schemas, semantics  # noqa: E402

BP = "ssot-documentation-reconcile"


def test_schema_valid_and_semantically_clean_document() -> None:
    doc = K.load(BP)
    errs = list(schemas.workflow_validator().iter_errors(doc))
    assert errs == [], [f"{'/'.join(str(p) for p in e.absolute_path)} [{e.validator}]" for e in errs[:5]]
    assert [r.to_json() for r in semantics.check_workflow(doc) if r.violations] == []


def test_all_seven_inline_work_units_pass_the_strict_profile() -> None:
    validator = schemas.work_unit_validator("strict")
    units = C.work_units(K.load(BP))
    assert len(units) == 7
    assert {u["id"] for u in units if list(validator.iter_errors(u))} == set()


# --------------------------------------------- property 1: authority by measurability


def test_authority_is_assigned_by_measurability() -> None:
    result = C.authority_is_assigned_by_measurability(K.load(BP))
    assert result.ok, result.why()


def test_control_removing_the_unverified_everywhere_escape_is_caught() -> None:
    """Both-states control: without the UNVERIFIED-everywhere branch, an unmeasurable fact would
    have to be blessed arbitrarily - which is the exact behaviour the card forbids."""
    mutated = K.mutate(
        K.load(BP),
        K.weaken_gate("authority-is-measurable", "authoritative_source_agrees_with_probe == true"),
    )
    K.assert_still_schema_valid(mutated)
    result = C.authority_is_assigned_by_measurability(mutated)
    assert not result.ok, "a gate with no honest fallback was accepted"
    assert any("fact_marked_unverified_everywhere" in r for r in result.reasons), result.reasons


def test_control_removing_the_probe_from_the_adjudicators_inputs_is_caught() -> None:
    """Both-states control: an adjudicator that never receives the probe is choosing authority by
    convenience, which is precisely the failure mode. The gate text alone would still look right."""
    mutated = K.mutate(K.load(BP), K.drop_work_unit_input("designate-authority", "measurability_probe"))
    K.assert_still_schema_valid(mutated)
    result = C.authority_is_assigned_by_measurability(mutated)
    assert not result.ok, "an adjudicator with no probe input was accepted"
    assert any("does not take the measurability probe" in r for r in result.reasons), result.reasons


def test_control_letting_the_rewrite_run_before_the_measurability_gate_is_caught() -> None:
    mutated = K.mutate(K.load(BP), K.drop_dependency("rewrite-as-pointers", "measurability-gate"))
    K.assert_still_schema_valid(mutated)
    result = C.authority_is_assigned_by_measurability(mutated)
    assert not result.ok, "the rewrite could run without an adjudicated authority"
    assert any("without the measurability gate" in r for r in result.reasons), result.reasons


# ---------------------------------------- property 2: no contradiction resolved silently


def test_no_contradiction_is_resolved_silently() -> None:
    result = C.no_contradiction_is_resolved_silently(K.load(BP))
    assert result.ok, result.why()


def test_control_dropping_the_silent_resolution_condition_is_caught() -> None:
    """Both-states control: the superseded register is what stops a corrected fact from being
    re-learned wrong. A gate that no longer requires it lets the correction vanish."""
    mutated = K.mutate(K.load(BP), K.weaken_gate("superseded-registered", "superseded_register_written == true"))
    K.assert_still_schema_valid(mutated)
    result = C.no_contradiction_is_resolved_silently(mutated)
    assert not result.ok, "a gate that permits silent resolution was accepted"
    assert any("contradictions_resolved_silently" in r for r in result.reasons), result.reasons


def test_control_removing_the_false_positive_control_is_caught() -> None:
    """Both-states control: without it, a sentence that legitimately repeats agreed context would
    be rewritten into a pointer - a worse outcome than leaving the contradiction alone."""
    mutated = K.mutate(K.load(BP), K.weaken_gate("no-legitimate-repeat-flagged", "statements_found > 0"))
    K.assert_still_schema_valid(mutated)
    result = C.no_contradiction_is_resolved_silently(mutated)
    assert not result.ok, "a reconcile with no false-positive control was accepted"
    assert any("false-positive control" in r for r in result.reasons), result.reasons


def test_control_registering_before_the_rewrite_is_caught() -> None:
    mutated = K.mutate(K.load(BP), K.drop_dependency("register-superseded", "rewrite-as-pointers"))
    K.assert_still_schema_valid(mutated)
    result = C.no_contradiction_is_resolved_silently(mutated)
    assert not result.ok, "a register that runs before the rewrite it records was accepted"
    assert any("after the rewrite" in r for r in result.reasons), result.reasons


# ---------------------------------------------- property 3: search completeness discipline


def test_a_missed_documentation_root_fails_rather_than_degrading() -> None:
    """A partial search leaves a contradiction live while reporting success, so this barrier is
    deliberately mode=all / on_partial=fail rather than proceed-degraded."""
    fan = C.stage(K.load(BP), "search-statements")
    assert fan is not None and fan["kind"] == "fanout"
    assert fan["on_item_failure"] == "abort"
    assert fan["barrier"]["mode"] == "all"
    assert fan["barrier"]["on_partial"] == "fail"
    join = C.stage(K.load(BP), "search-join")
    assert join["barrier"]["on_partial"] == "fail"


def test_the_search_records_its_own_term_list_so_a_missed_paraphrase_is_diagnosable() -> None:
    unit = C.stage(K.load(BP), "search-one-root")["work_unit"]
    assert "params.search_terms" in unit["inputs"]
    assert "search terms used" in unit["evidence_requirement"]
    assert any("paraphrase" in t for t in unit["tests_required"])


def test_the_rewrite_loop_is_bounded_and_reversible() -> None:
    conv = C.stage(K.load(BP), "rewrite-as-pointers")["convergence"]
    assert conv["max_iterations"] <= 10
    assert conv["no_progress_rounds"] >= 1
    assert C.identifiers(conv["converged_when"]) == {"unresolved_restatements"}
    unit = C.stage(K.load(BP), "rewrite-one-batch")["work_unit"]
    assert "before-text" in unit["evidence_requirement"], "an irreversible doc rewrite is not acceptable"
    assert any("byte-identical" in t for t in unit["tests_required"])


def test_the_drift_check_spec_must_be_falsifiable() -> None:
    """A gate that has never gone red is indistinguishable from a no-op, so the spec has to name a
    known-bad state and fail closed on an empty walk."""
    unit = C.stage(K.load(BP), "drift-check")["work_unit"]
    tests = " ".join(unit["tests_required"])
    assert "known-bad state" in tests
    assert "fail" in tests.lower() and "empty" in tests.lower()
    assert "no-op" in tests


def test_the_worked_example_uses_this_programs_own_measured_contradiction() -> None:
    """The example is grounded in a real three-value disagreement, and shows the probe overruling
    the most PROMINENT statement - which is the whole point of authority-by-measurability."""
    ext = K.load(BP)["x_extensions"]["bp7"]
    trace = " ".join(ext["worked_example"]["expected_trace"])
    assert "3 groups" in trace
    assert "LEGITIMATE-REPEAT" in trace, "the example never exercises the false-positive control"
    assert "was NOT chosen" in trace, "the example does not show the probe overruling prominence"
    assert ext["worked_example"]["expected_terminal_state"].startswith("SUCCESS:DOC-84")
