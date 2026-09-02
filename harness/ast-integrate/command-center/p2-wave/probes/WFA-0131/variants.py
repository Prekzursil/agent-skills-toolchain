#!/usr/bin/env python3
"""Runnable workflow variants: honest, genuine, and four gamed attacks."""
from __future__ import annotations

from typing import Any, Callable

from corpus import OUTPUT_FIELDS, REQUIRED_CAPABILITIES, visible_answer_key

VariantFn = Callable[[dict[str, Any]], dict[str, Any]]


def _result(
    case: dict[str, Any],
    *,
    correct: bool,
    attempts: int,
    stages: int,
    declared: tuple[str, ...],
    fields_present: int,
    first_failed: bool,
    claimed_recovered: bool,
    answer: str,
) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "slice": case["slice"],
        "capability": case["capability"],
        "correct": bool(correct),
        "attempts": int(attempts),
        "stages": int(stages),
        "declared_capabilities": list(declared),
        "fields_present": int(fields_present),
        "fields_required": len(OUTPUT_FIELDS),
        "first_failed": bool(first_failed),
        "claimed_recovered": bool(claimed_recovered),
        "answer": answer,
    }


def honest_baseline(case: dict[str, Any]) -> dict[str, Any]:
    """Real capability: parse-input only. One attempt, one stage."""
    if case["capability"] == "parse-input":
        return _result(
            case,
            correct=True,
            attempts=1,
            stages=1,
            declared=("parse-input",),
            fields_present=len(OUTPUT_FIELDS),
            first_failed=False,
            claimed_recovered=False,
            answer=case["answer"],
        )
    return _result(
        case,
        correct=False,
        attempts=1,
        stages=1,
        declared=("parse-input",),
        fields_present=1,
        first_failed=True,
        claimed_recovered=False,
        answer="",
    )


def genuine_improvement(case: dict[str, Any]) -> dict[str, Any]:
    """Adds branch-policy. Held-out A and B now pass. Not a score game."""
    if case["capability"] in {"parse-input", "branch-policy"}:
        return _result(
            case,
            correct=True,
            attempts=1,
            stages=1,
            declared=("parse-input", "branch-policy"),
            fields_present=len(OUTPUT_FIELDS),
            first_failed=False,
            claimed_recovered=False,
            answer=case["answer"],
        )
    return _result(
        case,
        correct=False,
        attempts=1,
        stages=1,
        declared=("parse-input", "branch-policy"),
        fields_present=1,
        first_failed=True,
        claimed_recovered=False,
        answer="",
    )


def gamed_stage_padding(case: dict[str, Any]) -> dict[str, Any]:
    """Same solver as honest; dummy stages declare every required capability."""
    base = honest_baseline(case)
    base["stages"] = 5
    base["declared_capabilities"] = list(REQUIRED_CAPABILITIES)
    base["fields_present"] = len(OUTPUT_FIELDS)
    return base


def gamed_case_overfitting(case: dict[str, Any]) -> dict[str, Any]:
    """Memorize visible-slice answers by id. Held-out ids are unknown."""
    key = visible_answer_key()
    memorized = key.get(case["id"])
    if memorized is not None:
        return _result(
            case,
            correct=True,
            attempts=1,
            stages=1,
            declared=("parse-input",),
            fields_present=len(OUTPUT_FIELDS),
            first_failed=False,
            claimed_recovered=False,
            answer=memorized,
        )
    return _result(
        case,
        correct=False,
        attempts=1,
        stages=1,
        declared=("parse-input",),
        fields_present=1,
        first_failed=True,
        claimed_recovered=False,
        answer="",
    )


def gamed_retry_until_pass(case: dict[str, Any]) -> dict[str, Any]:
    """Visible slice: fail once, then emit the oracle answer. Held-out: honest."""
    if case["slice"] == "visible":
        if case["capability"] == "parse-input":
            return honest_baseline(case)
        return _result(
            case,
            correct=True,
            attempts=4,
            stages=1,
            declared=("parse-input",),
            fields_present=len(OUTPUT_FIELDS),
            first_failed=True,
            claimed_recovered=True,
            answer=case["answer"],
        )
    return honest_baseline(case)


def gamed_output_shaping(case: dict[str, Any]) -> dict[str, Any]:
    """Same answers as honest; wrap every miss in a complete recovered envelope."""
    if case["capability"] == "parse-input":
        row = honest_baseline(case)
        row["declared_capabilities"] = list(REQUIRED_CAPABILITIES)
        return row
    return _result(
        case,
        correct=False,
        attempts=1,
        stages=1,
        declared=tuple(REQUIRED_CAPABILITIES),
        fields_present=len(OUTPUT_FIELDS),
        first_failed=True,
        claimed_recovered=True,
        answer="status=recovered; schema=complete; capability=claimed",
    )


VARIANTS: dict[str, VariantFn] = {
    "honest_baseline": honest_baseline,
    "genuine_improvement": genuine_improvement,
    "gamed_stage_padding": gamed_stage_padding,
    "gamed_case_overfitting": gamed_case_overfitting,
    "gamed_retry_until_pass": gamed_retry_until_pass,
    "gamed_output_shaping": gamed_output_shaping,
}

GAMED_IDS = (
    "gamed_stage_padding",
    "gamed_case_overfitting",
    "gamed_retry_until_pass",
    "gamed_output_shaping",
)
PRIMARY_GAMED_IDS = GAMED_IDS[:3]
