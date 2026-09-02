#!/usr/bin/env python3
"""A10 stopping-expression grammar (CNL-0010 surface, local to CNL-0128).

AND / OR / NOT, parenthesized groups, and IDENT OP VALUE with
OP in {==, !=, >=, <=, >, <}. VALUE is true, false, a number, or a
bare identifier (e.g. PASS).
"""
from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(
    r"""
    \s*
    (
        ==|!=|>=|<=|>|<
        | AND | OR | NOT
        | true | false
        | [A-Za-z_][A-Za-z0-9_]*
        | \d+(?:\.\d+)?
        | \( | \)
    )
    """,
    re.VERBOSE,
)

KNOWN_IDENTS = frozenset(
    {
        "unique_ideas",
        "completeness_score",
        "consensus",
        "no_new_objection_rounds",
        "no_new_counterexample_rounds",
        "unanimity",
        "max_rounds",
        "quality_gate",
        "unresolved_load_bearing_counterexample",
        "evidence_saturation",
        "time_minutes",
        "proof_of_impossibility",
        "minority_report",
    }
)


class ParseError(ValueError):
    pass


def tokenize(src: str) -> list[str]:
    pos = 0
    out: list[str] = []
    n = len(src)
    while pos < n:
        m = _TOKEN.match(src, pos)
        if not m:
            rest = src[pos:].strip()
            if not rest:
                break
            raise ParseError(f"unexpected at {pos}: {rest[:40]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


def parse(src: str) -> dict[str, Any]:
    if not isinstance(src, str):
        raise ParseError(f"stopping_expr must be a string, got {type(src).__name__}")
    tokens = tokenize(src)
    if not tokens:
        raise ParseError("empty stopping_expr")
    i = 0

    def peek() -> str | None:
        return tokens[i] if i < len(tokens) else None

    def eat(expected: str | None = None) -> str:
        nonlocal i
        if i >= len(tokens):
            raise ParseError("unexpected end of expression")
        tok = tokens[i]
        if expected is not None and tok != expected:
            raise ParseError(f"expected {expected!r} got {tok!r}")
        i += 1
        return tok

    def parse_or() -> dict[str, Any]:
        node = parse_and()
        while peek() == "OR":
            eat("OR")
            node = {"op": "OR", "left": node, "right": parse_and()}
        return node

    def parse_and() -> dict[str, Any]:
        node = parse_not()
        while peek() == "AND":
            eat("AND")
            node = {"op": "AND", "left": node, "right": parse_not()}
        return node

    def parse_not() -> dict[str, Any]:
        if peek() == "NOT":
            eat("NOT")
            return {"op": "NOT", "arg": parse_not()}
        return parse_atom()

    def parse_atom() -> dict[str, Any]:
        if peek() == "(":
            eat("(")
            node = parse_or()
            eat(")")
            return node
        ident = eat()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ident):
            raise ParseError(f"expected identifier, got {ident!r}")
        if peek() in {"==", "!=", ">=", "<=", ">", "<"}:
            op = eat()
            raw = eat()
            return {"op": op, "ident": ident, "value": _value(raw)}
        return {"op": "IDENT", "ident": ident}

    tree = parse_or()
    if i != len(tokens):
        raise ParseError(f"trailing tokens: {tokens[i:]}")
    return {"source": src, "tokens": tokens, "ast": tree}


def _value(raw: str) -> Any:
    if raw == "true":
        return True
    if raw == "false":
        return False
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    if re.fullmatch(r"\d+\.\d+", raw):
        return float(raw)
    return raw


def collect_idents(ast: dict[str, Any]) -> set[str]:
    op = ast.get("op")
    if op in {"AND", "OR"}:
        return collect_idents(ast["left"]) | collect_idents(ast["right"])
    if op == "NOT":
        return collect_idents(ast["arg"])
    ident = ast.get("ident")
    return {ident} if isinstance(ident, str) else set()


def _cmp_atoms(ast: dict[str, Any]) -> list[tuple[str, str, Any]]:
    op = ast.get("op")
    if op in {"AND", "OR"}:
        return _cmp_atoms(ast["left"]) + _cmp_atoms(ast["right"])
    if op == "NOT":
        return []
    if op in {"==", "!=", ">=", "<=", ">", "<"}:
        return [(str(ast["ident"]), str(op), ast.get("value"))]
    return []


def statically_unsatisfiable(ast: dict[str, Any]) -> bool:
    """Conservative static unsat: x AND NOT x, or contradictory AND-comparisons."""
    op = ast.get("op")
    if op == "AND":
        left, right = ast["left"], ast["right"]
        if left.get("op") == "NOT" and _ast_equal(left.get("arg") or {}, right):
            return True
        if right.get("op") == "NOT" and _ast_equal(right.get("arg") or {}, left):
            return True
        if statically_unsatisfiable(left) or statically_unsatisfiable(right):
            return True
        atoms = _cmp_atoms(left) + _cmp_atoms(right)
        by_ident: dict[str, list[tuple[str, Any]]] = {}
        for ident, cop, val in atoms:
            by_ident.setdefault(ident, []).append((cop, val))
        for pairs in by_ident.values():
            ops = {(o, v) for o, v in pairs}
            for o, v in list(ops):
                if o == ">=" and ("<", v) in ops:
                    return True
                if o == ">" and ("<=", v) in ops:
                    return True
                if o == "==" and ("==", _negate_eq(v)) in ops:
                    return True
                if o == "==":
                    for o2, v2 in ops:
                        if o2 == "==" and v2 != v:
                            return True
                        if o2 == "<" and _numeric(v) and _numeric(v2) and not (v < v2):
                            return True
                        if o2 == ">" and _numeric(v) and _numeric(v2) and not (v > v2):
                            return True
                        if o2 == "<=" and _numeric(v) and _numeric(v2) and not (v <= v2):
                            return True
                        if o2 == ">=" and _numeric(v) and _numeric(v2) and not (v >= v2):
                            return True
        return False
    if op in {"OR", "NOT"}:
        return False
    return False


def _negate_eq(v: Any) -> Any:
    if v is True:
        return False
    if v is False:
        return True
    return object()


def _numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _ast_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a == b


def diagnose(src: Any) -> dict[str, Any]:
    """Return parse/static diagnosis. Never raises."""
    try:
        tree = parse(src)
    except ParseError as exc:
        return {
            "ok": False,
            "code": "parse-error",
            "message": str(exc),
            "unbound": [],
            "unsat": False,
        }
    unbound = sorted(collect_idents(tree["ast"]) - KNOWN_IDENTS)
    unsat = statically_unsatisfiable(tree["ast"])
    if unbound:
        return {
            "ok": False,
            "code": "unbound-ident",
            "message": "unbound identifier(s): " + ", ".join(unbound),
            "unbound": unbound,
            "unsat": unsat,
            "ast": tree["ast"],
        }
    if unsat:
        return {
            "ok": False,
            "code": "statically-unsatisfiable",
            "message": "stopping_expr is statically unsatisfiable",
            "unbound": [],
            "unsat": True,
            "ast": tree["ast"],
        }
    return {
        "ok": True,
        "code": "ok",
        "message": "accepted",
        "unbound": [],
        "unsat": False,
        "ast": tree["ast"],
        "idents": sorted(collect_idents(tree["ast"])),
    }
