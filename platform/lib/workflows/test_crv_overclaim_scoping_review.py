"""End-to-end test for FLAGSHIP blueprint BP-CRV-05 (card 53), crv.overclaim-scoping-review.

Mechanism protected: an overclaim is a REFUTED verdict even when the code is fine; the residual
must be disclosed INLINE (a trailing limitations section does not count); and a genuine defect
may not be softened into a scoping note.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

SLUG = "crv.overclaim-scoping-review"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_asserted_scope_is_measured_before_evidence_scope_and_both_before_the_verdict() -> None:
    """Order is the mechanism: you cannot compare two widths until both are measured."""
    d = doc()
    kit.assert_precedes(d, "extract-asserted-scope", "measure-evidence-scope")
    kit.assert_precedes(d, "measure-evidence-scope", "classify-width")
    kit.assert_precedes(d, "classify-width", "rescope-sentence")


def test_the_rewrite_stage_only_runs_when_an_overclaim_was_found() -> None:
    d = doc()
    stage = next(s for s in d["stages"] if s["id"] == "rescope-sentence")
    assert "overclaims_found" in str(stage["when"]), "the rewrite is not conditional on a finding"
    ctx = kit.worked_context(d)
    assert _expr.evaluate(stage["when"], ctx, strict=True) is True
    assert _expr.evaluate(stage["when"], {**ctx, "overclaims_found": 0}, strict=True) is False


def test_inline_adjacency_rejects_a_trailing_limitations_section() -> None:
    """The measured failure: 40% of UNVERIFIED tags sat in the final 15% of their document."""
    d = doc()
    assert kit.evaluate_gate(d, "inline-adjacency") is True
    assert (
        kit.evaluate_gate(
            d,
            "inline-adjacency",
            {"residual_disclosed_inline": False, "trailing_limitations_section_used_as_substitute": True},
        )
        is False
    )
    # a trailing section is not merely insufficient on its own - it is rejected as a SUBSTITUTE
    assert (
        kit.evaluate_gate(d, "inline-adjacency", {"trailing_limitations_section_used_as_substitute": True})
        is False
    )


def test_defect_not_softened_is_a_veto_gate_not_advisory() -> None:
    """Without this, the blueprint becomes a route to reclassify real defects as wording."""
    d = doc()
    gate = d["gates"]["defect-not-softened"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert kit.evaluate_gate(d, "defect-not-softened") is True
    assert kit.evaluate_gate(d, "defect-not-softened", {"genuine_defects_classed_as_overclaim": 1}) is False
    assert d["roles"]["defect-police"]["authority"] == "veto"
    assert d["roles"]["defect-police"]["independence"] == "cross-examining"


def test_every_refuted_overclaim_must_carry_a_replacement_sentence() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "rescoped-sentence-supplied") is True
    assert (
        kit.evaluate_gate(d, "rescoped-sentence-supplied", {"refuted_overclaims_without_rescoped_sentence": 2})
        is False
    ), "a refuted overclaim with no rewritten sentence is an incomplete review, not a pass"


def test_every_residual_names_its_settling_experiment() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "settling-experiment-named") is True
    assert (
        kit.evaluate_gate(d, "settling-experiment-named", {"residuals_without_settling_experiment": 1})
        is False
    )


def test_the_stopping_rule_cannot_fire_before_any_claim_is_reviewed() -> None:
    """A cheap stopping rule with no floor lets a workflow stop having done nothing."""
    d = doc()
    rule = next(r for r in d["stopping_rules"] if r["id"] == "every-claim-has-a-verdict")
    floor = rule["minimum_conditions"]
    ctx = kit.worked_context(d)
    assert _expr.evaluate(floor, ctx, strict=True) is True
    assert _expr.evaluate(floor, {**ctx, "claims_reviewed": 0}, strict=True) is False, (
        "with zero claims reviewed the rule would still be allowed to fire"
    )


def test_the_document_records_its_measured_basis_rather_than_asserting_a_ratio() -> None:
    x = doc()["x_extensions"]
    assert "5 of 8" in x["measured_basis"], "the 5-of-8 measurement is the reason this blueprint exists"
    assert "UNVERIFIED" in x["unverified"]
    assert "settling experiment" in x["unverified"], "no named experiment for the residual"


def test_MUTATION_weakening_inline_adjacency_removes_its_power() -> None:
    d = doc()
    bad = {"residual_disclosed_inline": False, "trailing_limitations_section_used_as_substitute": True}
    assert kit.evaluate_gate(d, "inline-adjacency", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["inline-adjacency"]["expression"] = "claims_reviewed >= 1"
    ctx = kit.worked_context(weakened)
    ctx.update(bad)
    assert _expr.evaluate(weakened["gates"]["inline-adjacency"]["expression"], ctx, strict=True) is True


def test_MUTATION_dropping_the_defect_police_gate_is_rejected() -> None:
    kit.assert_rejected(kit.drop_stage(doc(), "defect-not-softened"), "defect-police gate removed")


def test_MUTATION_removing_the_stopping_floor_is_visible_to_the_slice_test() -> None:
    """A floor deleted from the document is not a schema error - minimum_conditions is optional -
    so it must be caught behaviourally. This asserts the floor is what blocks an empty run."""
    d = kit.mutated(doc())
    rule = next(r for r in d["stopping_rules"] if r["id"] == "every-claim-has-a-verdict")
    del rule["minimum_conditions"]
    assert not kit.schema_errors(d), "removing an optional floor is legal to the schema"
    assert "minimum_conditions" not in rule
    # ...and with the floor gone the rule fires on a run that reviewed nothing
    ctx = {**kit.worked_context(d), "claims_reviewed": 0}
    assert _expr.evaluate(rule["expression"], ctx, strict=True) is True, (
        "the floor was the only thing preventing a zero-claim stop; that is why it is present"
    )
