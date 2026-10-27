"""Three-valued (F/U/T) stopping-expression evaluator bound by CNF-0089.

The recorded conformance binds THIS module as the evaluator the driver
executes (tools/council/stopping/expr.py is absent on this worktree).
Kleene semantics: AND is false-anchored, OR is true-anchored; a STOP is
emitted exactly when the expression evaluates to T.
"""
from __future__ import annotations

F, U, T = "F", "U", "T"


def atom(name: str, state: dict) -> str:
    """Evaluate one atomic predicate against the driven state.

    Atoms are recorded in the artifact as '<var> <op> <const>' strings.
    A state value of the sentinel string 'NOT-CHECKED' denotes U.
    """
    parts = name.split()
    var, op, const = parts[0], parts[1], " ".join(parts[2:])
    val = state.get(var, U)
    if val == "NOT-CHECKED":
        return U
    if op in (">=", ">", "<=", "<"):
        try:
            c = float(const)
            v = float(val)
        except (TypeError, ValueError):
            return U
        if op == ">=":
            return T if v >= c else F
        if op == ">":
            return T if v > c else F
        if op == "<=":
            return T if v <= c else F
        return T if v < c else F
    if op == "==":
        if const in ("true", "PASS", "0"):
            want = {"true": True, "PASS": "PASS", "0": 0}[const]
            return T if val == want else F
        return T if str(val) == const else F
    return U


def conj(a: str, b: str) -> str:
    if a == F or b == F:
        return F
    if a == U or b == U:
        return U
    return T


def disj(a: str, b: str) -> str:
    if a == T or b == T:
        return T
    if a == U or b == U:
        return U
    return F


def evaluate(expression: str, state: dict) -> str:
    """Evaluate a two-atom expression with one AND/OR connective (Kleene)."""
    up = _split_top(expression)
    if up is None:
        return atom(expression.strip(), state)
    left, conn, right = up
    lv = evaluate(left, state)
    rv = evaluate(right, state)
    return conj(lv, rv) if conn == "AND" else disj(lv, rv)


def decide(expression: str, state: dict) -> str:
    """Return 'STOP' exactly when the expression evaluates T, else 'CONTINUE'."""
    return "STOP" if evaluate(expression, state) == T else "CONTINUE"


def _split_top(expr: str):
    for conn in (" AND ", " OR "):
        if conn in expr:
            left, right = expr.split(conn, 1)
            return left, conn.strip(), right
    return None
