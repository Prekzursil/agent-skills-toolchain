"""Tests for the stopping/convergence expression grammar.

The six spec-mandated expressions (``_USER-PROMPTS.md:10937-10942``) are the headline cases:
they must PARSE, must evaluate TRUE on a satisfying context and FALSE on a falsifying one
(a parser that returns True for everything would pass a one-sided test).
"""

from __future__ import annotations

import pytest

from wfdsl import expr
from wfdsl.validate import SPEC_STOPPING_CONTEXT, SPEC_STOPPING_EXPRESSIONS

FALSIFYING = {
    "unique_ideas": 12,
    "completeness_score": 0.10,
    "consensus": 0.20,
    "no_new_objection_rounds": 0,
    "unanimity": False,
    "max_rounds": 3,
    "quality_gate": "FAIL",
    "unresolved_load_bearing_counterexample": 4,
    "evidence_saturation": False,
    "time_minutes": 5,
    "proof_of_impossibility": False,
}


@pytest.mark.parametrize("text", SPEC_STOPPING_EXPRESSIONS)
def test_spec_expression_parses(text: str) -> None:
    ast = expr.parse(text)
    assert ast.identifiers(), f"no identifiers extracted from {text!r}"


@pytest.mark.parametrize("text", SPEC_STOPPING_EXPRESSIONS)
def test_spec_expression_true_on_satisfying_context(text: str) -> None:
    assert expr.evaluate(text, SPEC_STOPPING_CONTEXT) is True


@pytest.mark.parametrize("text", SPEC_STOPPING_EXPRESSIONS)
def test_spec_expression_false_on_falsifying_context(text: str) -> None:
    """Both-states control: an evaluator that always returns True must fail here."""
    assert expr.evaluate(text, FALSIFYING) is False


def test_precedence_not_binds_tighter_than_and_which_binds_tighter_than_or() -> None:
    ctx = {"a": True, "b": False, "c": True}
    assert expr.evaluate("a AND b OR c", ctx) is True  # (a AND b) OR c
    assert expr.evaluate("a AND (b OR c)", ctx) is True
    assert expr.evaluate("NOT b AND a", ctx) is True  # (NOT b) AND a
    assert expr.evaluate("NOT (b AND a)", ctx) is True
    assert expr.evaluate("b OR (a AND b)", ctx) is False


def test_case_insensitive_keywords_and_symbolic_operators() -> None:
    ctx = {"x": 5, "y": 1}
    assert expr.evaluate("x >= 5 and y == 1", ctx) is True
    assert expr.evaluate("x >= 5 && y == 1", ctx) is True
    assert expr.evaluate("x < 5 || y == 1", ctx) is True
    assert expr.evaluate("!(x < 5)", ctx) is True


def test_bare_identifier_on_the_right_is_a_symbolic_constant() -> None:
    assert expr.evaluate("verdict == CONFIRMED", {"verdict": "CONFIRMED"}) is True
    assert expr.evaluate("verdict == CONFIRMED", {"verdict": "REFUTED"}) is False


def test_unknown_left_identifier_raises_instead_of_silently_reading_false() -> None:
    with pytest.raises(expr.UnknownIdentifier):
        expr.evaluate("unmeasured_metric >= 1", {})
    # opt-out exists, but it must be explicit
    assert expr.evaluate("unmeasured_metric >= 1", {}, strict=False) is False


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "unique_ideas >>>= AND",
        "AND consensus",
        "(consensus >= 0.9",
        "consensus >= 0.9)",
        "consensus 0.9",
        "consensus >= ",
        "consensus >= 0.9 AND",
        "@@@",
    ],
)
def test_malformed_expressions_are_rejected(bad: str) -> None:
    with pytest.raises(expr.ExpressionError):
        expr.parse(bad)


def test_structured_forms_evaluate() -> None:
    ctx = {"unique_ideas": 120, "completeness_score": 0.95, "flag": False}
    assert (
        expr.evaluate(
            {"all": ["unique_ideas >= 100", "completeness_score >= 0.9"]}, ctx
        )
        is True
    )
    assert (
        expr.evaluate(
            {"any": ["unique_ideas >= 500", "completeness_score >= 0.9"]}, ctx
        )
        is True
    )
    assert expr.evaluate({"not": "flag"}, ctx) is True
    assert (
        expr.evaluate({"cmp": {"left": "unique_ideas", "op": ">=", "right": 100}}, ctx)
        is True
    )
    assert (
        expr.evaluate(
            {
                "weighted": {
                    "terms": [
                        {"expr": "unique_ideas >= 100", "weight": 0.5},
                        {"expr": "flag", "weight": 0.5},
                    ],
                    "threshold": 0.8,
                }
            },
            ctx,
        )
        is False
    )
    assert (
        expr.evaluate(
            {
                "weighted": {
                    "terms": [
                        {"expr": "unique_ideas >= 100", "weight": 0.6},
                        {"expr": "completeness_score >= 0.9", "weight": 0.4},
                    ],
                    "threshold": 0.8,
                }
            },
            ctx,
        )
        is True
    )


def test_structured_and_string_forms_agree() -> None:
    ctx = {"unique_ideas": 104, "completeness_score": 0.93}
    string_form = "unique_ideas >= 100 AND completeness_score >= 0.90"
    structured = {
        "all": [
            {"cmp": {"left": "unique_ideas", "op": ">=", "right": 100}},
            {"cmp": {"left": "completeness_score", "op": ">=", "right": 0.9}},
        ]
    }
    assert expr.evaluate(string_form, ctx) == expr.evaluate(structured, ctx) is True


def test_ordering_comparison_on_non_numbers_is_an_error_not_a_silent_false() -> None:
    with pytest.raises(expr.ExpressionError):
        expr.evaluate("name > 3", {"name": "alpha"})


def test_identifiers_excludes_symbolic_right_hand_constants() -> None:
    assert expr.identifiers("quality_gate == PASS") == {"quality_gate"}
    assert expr.identifiers("a >= 1 AND b <= c") == {"a", "b", "c"}


def test_agrees_with_councilspec_on_spec_examples() -> None:
    """Cross-implementation second signal: two independent parsers, one verdict each.

    ``councilspec.expression`` is a sibling contract unit with a CLOSED metric vocabulary.
    Where it accepts one of the six spec expressions, its evaluation must agree with ours.
    Where it rejects one (because a metric is not in its registry), that is a scope
    difference, reported here rather than silently ignored.
    """
    council_expr = pytest.importorskip(
        "councilspec.expression", reason="sibling councilspec unit not present"
    )
    agreed, scope_diff = [], []
    for text in SPEC_STOPPING_EXPRESSIONS:
        try:
            tree = council_expr.parse(text)
            theirs = council_expr.evaluate(tree, SPEC_STOPPING_CONTEXT)
        except Exception as exc:  # noqa: BLE001 - a rejection is data, not a failure
            scope_diff.append((text, type(exc).__name__))
            continue
        ours = expr.evaluate(text, SPEC_STOPPING_CONTEXT)
        assert ours == theirs, (
            f"parsers disagree on {text!r}: wfdsl={ours} councilspec={theirs}"
        )
        agreed.append(text)
    assert agreed or scope_diff, "no expression was compared at all"
    print(
        f"councilspec agreement: {len(agreed)}/{len(SPEC_STOPPING_EXPRESSIONS)} compared; scope differences: {scope_diff}"
    )
