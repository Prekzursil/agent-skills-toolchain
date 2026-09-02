#!/usr/bin/env python3
"""Independent predicates: one Python function per expression id.

Does not lex or parse the expression string. A disagreement with expr.py
blocks the unit (reviewer recount).
"""
from __future__ import annotations

from typing import Any, Callable

Predicate = Callable[[dict[str, Any]], bool | None]


def _num(metrics: dict[str, Any], key: str) -> float | None:
    if key not in metrics:
        return None
    return float(metrics[key])


def _bool(metrics: dict[str, Any], key: str) -> bool | None:
    if key not in metrics:
        return None
    return bool(metrics[key]) is True


def _and(a: bool | None, b: bool | None) -> bool | None:
    if a is False or b is False:
        return False
    if a is None or b is None:
        return None
    return True


def _or(a: bool | None, b: bool | None) -> bool | None:
    if a is True or b is True:
        return True
    if a is None or b is None:
        return None
    return False


def e1(m: dict[str, Any]) -> bool | None:
    u = _num(m, "unique_ideas")
    c = _num(m, "completeness_score")
    left = None if u is None else u >= 100
    right = None if c is None else c >= 0.90
    return _and(left, right)


def e2(m: dict[str, Any]) -> bool | None:
    c = _num(m, "consensus")
    r = _num(m, "no_new_objection_rounds")
    left = None if c is None else c >= 0.95
    right = None if r is None else r >= 2
    return _and(left, right)


def e3(m: dict[str, Any]) -> bool | None:
    u = _bool(m, "unanimity")
    r = _num(m, "max_rounds")
    right = None if r is None else r == 12
    return _or(u, right)


def e4(m: dict[str, Any]) -> bool | None:
    g = m.get("quality_gate")
    left = None if "quality_gate" not in m else g == "PASS"
    n = _num(m, "unresolved_load_bearing_counterexample")
    right = None if n is None else n == 0
    return _and(left, right)


def e5(m: dict[str, Any]) -> bool | None:
    s = _bool(m, "evidence_saturation")
    t = _num(m, "time_minutes")
    right = None if t is None else t >= 180
    return _or(s, right)


def e6(m: dict[str, Any]) -> bool | None:
    if "proof_of_impossibility" not in m:
        return None
    return m["proof_of_impossibility"] is True


PREDICATES: dict[str, Predicate] = {
    "E1": e1,
    "E2": e2,
    "E3": e3,
    "E4": e4,
    "E5": e5,
    "E6": e6,
}


def evaluate_id(expression_id: str, metrics: dict[str, Any]) -> bool | None:
    fn = PREDICATES[expression_id]
    return fn(metrics)
