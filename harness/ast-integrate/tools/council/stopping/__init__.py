"""Council stopping rules: when a deliberation is allowed (or forced) to stop.

Submodules (each importable on its own):

* :mod:`~council.stopping.expr` - composable Boolean stopping expressions
  (``AND``/``OR``/``NOT``/``ANY``/``ALL``/``WEIGHTED``): parser, strict binder against
  runtime producers, and a Kleene three-valued evaluator in which NOT-CHECKED never stops.
* :mod:`~council.stopping.minimum` - minimum-deliberation floors (min rounds, independent
  briefs, objections considered) that block an instant consensus.
* :mod:`~council.stopping.deadlock` - deadlock detector with separate TPR/FPR and the
  escalation ladder.
* :mod:`~council.stopping.evidence_saturation` - yield-collapse detector for the
  ``evidence_saturation`` metric.
* :mod:`~council.stopping.spec_examples` - the six catalog stopping examples with their
  fire / silent / NOT-CHECKED fixtures.

The expression surface is re-exported here so ``from council.stopping import parse`` works;
the concrete gates keep their own namespaces.
"""
from __future__ import annotations

from . import expr
from .expr import (
    LIVE_RUN_ROUNDS,
    NOT_CHECKED,
    SPEC_EXPRESSIONS,
    BindError,
    BoundExpression,
    EvalResult,
    EvaluationError,
    Node,
    ParseError,
    SpecValidationError,
    StoppingExprError,
    ast_to_dict,
    bind,
    census,
    evaluate,
    evaluate_source,
    is_not_checked,
    live_run,
    parse,
    referenced_metrics,
    run_fixture,
    spec_producers,
    validate_spec,
)

__all__ = [
    # submodules
    "deadlock",
    "evidence_saturation",
    "expr",
    "minimum",
    "spec_examples",
    # expression surface
    "LIVE_RUN_ROUNDS",
    "NOT_CHECKED",
    "SPEC_EXPRESSIONS",
    "BindError",
    "BoundExpression",
    "EvalResult",
    "EvaluationError",
    "Node",
    "ParseError",
    "SpecValidationError",
    "StoppingExprError",
    "ast_to_dict",
    "bind",
    "census",
    "evaluate",
    "evaluate_source",
    "is_not_checked",
    "live_run",
    "parse",
    "referenced_metrics",
    "run_fixture",
    "spec_producers",
    "validate_spec",
]
