"""End-to-end tests for blueprint 78, BP-UX-02 two-track-ui-audit-rubric-verdict (FLAGSHIP).

The two-track split is only real if the judgement half is ANSWERABLE to the measurement half.
Three properties encode that and each carries a mutation control:
  * a measured critical error CAPS the composite (it is not averaged into it),
  * Track B makes exactly ONE scoring call per rubric dimension, and
  * the workflow is READ-ONLY by construction - it cannot change what it measures.
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

BP = "two-track-ui-audit-rubric-verdict"


def test_schema_valid_and_semantically_clean_including_the_council_advisory() -> None:
    """DSL-SEM-014 is ADVISORY, and it is the one that caught the council rule text: the DSL
    tokenizer rejects councilspec's `custom:` prefix, so a council stopping rule must use registry
    metrics only. Zero advisories here means both parsers accept the same text."""
    doc = K.load(BP)
    errs = list(schemas.workflow_validator().iter_errors(doc))
    assert errs == [], [
        f"{'/'.join(str(p) for p in e.absolute_path)} [{e.validator}]" for e in errs[:5]
    ]
    results = semantics.check_workflow(doc)
    assert [r.to_json() for r in results if r.violations] == []
    advisories = [
        r.to_json() for r in results if r.severity == "advisory" and r.violations
    ]
    assert advisories == [], advisories


# --------------------------------------- property 1: a critical error CAPS the composite


def test_critical_error_caps_the_composite() -> None:
    result = C.critical_error_caps_the_composite(K.load(BP))
    assert result.ok, result.why()


def test_control_making_the_cap_gate_vacuous_is_caught() -> None:
    """Both-states control: with a vacuous cap gate, one hard contrast failure could be diluted by
    eight good dimensions into a passing composite - the exact averaging this blueprint forbids."""
    mutated = K.mutate(
        K.load(BP), K.weaken_gate("critical-error-caps", "composite >= 0")
    )
    K.assert_still_schema_valid(mutated)
    result = C.critical_error_caps_the_composite(mutated)
    assert not result.ok, "a vacuous cap gate was accepted"
    assert any("does not bound composite by the cap" in r for r in result.reasons), (
        result.reasons
    )


def test_control_inverting_the_cap_comparison_is_caught() -> None:
    """Both-states control: `composite >= critical_error_cap` mentions both identifiers and is
    still wrong. A predicate that only checked identifier presence would pass this."""
    mutated = K.mutate(
        K.load(BP),
        K.weaken_gate("critical-error-caps", "composite >= critical_error_cap"),
    )
    K.assert_still_schema_valid(mutated)
    result = C.critical_error_caps_the_composite(mutated)
    assert not result.ok, "an inverted cap comparison was accepted"
    assert any("does not express an upper bound" in r for r in result.reasons), (
        result.reasons
    )


def test_control_computing_the_cap_before_the_consistency_check_is_caught() -> None:
    mutated = K.mutate(
        K.load(BP), K.drop_dependency("apply-critical-override", "consistency-gate")
    )
    K.assert_still_schema_valid(mutated)
    result = C.critical_error_caps_the_composite(mutated)
    assert not result.ok, "the cap could be computed from unchecked scores"
    assert any(
        "before Track B is checked against Track A" in r for r in result.reasons
    ), result.reasons


# ------------------------------------- property 2: one scoring call per rubric dimension


def test_one_scoring_call_per_dimension() -> None:
    result = C.one_scoring_call_per_dimension(K.load(BP))
    assert result.ok, result.why()


def test_control_adding_a_second_scoring_task_to_the_fanout_body_is_caught() -> None:
    """Both-states control: two scoring tasks per fan-out item means one call can trade one
    dimension off against another, which is what the one-call protocol exists to prevent."""
    mutated = K.mutate(
        K.load(BP),
        K.duplicate_fanout_body_task("score-track-b", "score-dimension-extra"),
    )
    K.assert_still_schema_valid(mutated)
    result = C.one_scoring_call_per_dimension(mutated)
    assert not result.ok, "a fan-out body with two scoring tasks was accepted"
    assert any("scoring tasks" in r for r in result.reasons), result.reasons


def test_control_weakening_the_protocol_gate_is_caught() -> None:
    mutated = K.mutate(
        K.load(BP), K.weaken_gate("one-call-per-dimension", "scoring_calls >= 1")
    )
    K.assert_still_schema_valid(mutated)
    result = C.one_scoring_call_per_dimension(mutated)
    assert not result.ok, "a protocol gate that counts nothing was accepted"
    assert any("multi_dimension_calls" in r for r in result.reasons), result.reasons


# ------------------------------------------------- property 3: read-only by construction


def test_the_audit_cannot_edit_what_it_measures() -> None:
    """READ-ONLY is claimed in the card. It is only true if Edit and the app write paths are
    DENIED rather than merely unused - an unused-but-allowed tool is one prompt away from a write."""
    policy = K.load(BP)["tool_policy"]
    assert policy["default"] == "deny"
    denied = set(policy["deny"])
    assert {"Edit", "Write(app/**)", "Write(src/**)"} <= denied, denied
    assert "app/**" in policy["forbid_write_paths"]
    for role in K.load(BP)["roles"].values():
        assert "Edit" not in (role.get("tool_permissions") or [])
        assert role.get("write_paths") in (None, []), role


def test_an_unavailable_engine_excludes_its_dimension_with_the_exclusion_stated() -> (
    None
):
    doc = K.load(BP)
    ids = C.identifiers(C.gate_expression(doc, "exclusion-gate"))
    assert "unknown_dimensions_have_stated_exclusion" in ids
    collectors = C.stage(doc, "collect-track-a")
    assert collectors["on_item_failure"] == "continue", (
        "an unavailable engine must not abort the audit"
    )
    assert collectors["barrier"]["on_partial"] == "proceed-degraded"
    body_unit = collectors["body"][0]["work_unit"]
    assert any("UNAVAILABLE" in t for t in body_unit["tests_required"])


def test_the_cross_vendor_critic_is_a_council_stage_with_a_bounded_stopping_rule() -> (
    None
):
    council = C.stage(K.load(BP), "reconcile-with-critic")
    assert council is not None and council["kind"] == "council"
    assert council["participants_min"] == 2 and council["participants_max"] == 2
    assert len(council["stopping_rules"]) >= 1
    ext = K.load(BP)["x_extensions"]["bp7"]
    assert "council_expression_encoding_note" in ext, (
        "the registry-metric encoding of the conservative-reconciliation rule must be stated, or a "
        "reader will take minority_report_present literally"
    )


def test_the_worked_example_shows_the_cap_changing_the_number() -> None:
    """A cap that never changes the composite is decorative. The example must show both numbers."""
    trace = " ".join(
        K.load(BP)["x_extensions"]["bp7"]["worked_example"]["expected_trace"]
    )
    assert "3.4" in trace and "2.0" in trace, trace
    assert "BOTH numbers are recorded" in trace
    assert "UNKNOWN" in trace, "the example never exercises the excluded-dimension path"
