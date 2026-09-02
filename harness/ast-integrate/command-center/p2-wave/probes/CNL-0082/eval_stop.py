#!/usr/bin/env python3
"""Evaluate the spec expression with three-valued OR.

Arm attribution is mandatory: a time-minutes hit must not be recorded as
evidence_saturation, and a never-firing detector must stay visible as
saturation_arm=false rather than being masked by the disjunction.
"""
from __future__ import annotations

from typing import Any

from a10_grammar import SPEC_EXPR, parse
from saturation import detect

NOT_CHECKED = "NOT-CHECKED"
TIME_FLOOR = 180


def _or3(a: Any, b: Any) -> Any:
    if a is True or b is True:
        return True
    if a is False and b is False:
        return False
    return NOT_CHECKED


def eval_bindings(sat: Any, time_minutes: Any) -> dict[str, Any]:
    sat_arm: Any = NOT_CHECKED if sat is None else bool(sat)
    time_arm: Any = (
        NOT_CHECKED if time_minutes is None else int(time_minutes) >= TIME_FLOOR
    )
    value = _or3(sat_arm, time_arm)
    if value is True:
        if sat_arm is True and time_arm is True:
            which = "both"
        elif sat_arm is True:
            which = "evidence_saturation"
        else:
            which = "time_minutes"
    elif value is False:
        which = "none"
    else:
        which = "not-checked"
    return {
        "expression_verbatim": SPEC_EXPR,
        "evidence_saturation": sat_arm,
        "time_minutes": time_minutes,
        "time_arm": time_arm,
        "saturation_arm": sat_arm is True,
        "value": value,
        "fires": value is True,
        "which_arm": which,
        "time_floor": TIME_FLOOR,
    }


def evaluate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    ast = parse(SPEC_EXPR)
    det = detect(fixture)
    bound = eval_bindings(det["evidence_saturation"], fixture.get("time_minutes"))
    return {
        "fixture_id": fixture.get("id"),
        "ast": ast,
        "detector": det,
        "decision": bound,
        "expected_fire": fixture.get("expected_fire"),
        "expected_arm": fixture.get("expected_arm"),
        "expected_saturation": fixture.get("expected_saturation"),
        "expected_reason": fixture.get("expected_reason"),
    }
