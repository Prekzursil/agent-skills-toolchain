#!/usr/bin/env python3
"""A10 stopping-expression grammar (CNL-0010 surface, local to this unit).

Accepts AND / OR / NOT, parenthesized groups, and comparison atoms
IDENT OP VALUE with OP in {==, !=, >=, <=, >, <}. VALUE is true, false,
a number, or a bare identifier (e.g. PASS).

"Unchanged" means the spec string parses as written: no rewrite to a
different surface form is required for acceptance.
"""
from __future__ import annotations

import re
from typing import Any

SPEC_EXAMPLES = (
    ("10937", "unique_ideas >= 100 AND completeness_score >= 0.90"),
    ("10938", "consensus >= 0.95 AND no_new_objection_rounds >= 2"),
    ("10939", "unanimity == true OR max_rounds == 12"),
    ("10940", "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0"),
    ("10941", "evidence_saturation == true OR time_minutes >= 180"),
    ("10942", "proof_of_impossibility == true"),
)

UNIT_EXPRESSION = "proof_of_impossibility == true"

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
    tokens = tokenize(src)
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


def accepts_unchanged(src: str) -> tuple[bool, str]:
    try:
        tree = parse(src)
    except ParseError as exc:
        return False, f"parse-error:{exc}"
    if tree["source"] != src:
        return False, "source-rewritten"
    if tokenize(src) != tree["tokens"]:
        return False, "token-rewrite"
    return True, "accepted-unchanged"


def parse_all_spec_examples() -> list[dict[str, Any]]:
    rows = []
    for line, expr in SPEC_EXAMPLES:
        ok, why = accepts_unchanged(expr)
        rows.append({"line": line, "expression": expr, "accepted": ok, "why": why})
    return rows


def eval_ast(ast: dict[str, Any], bindings: dict[str, Any]) -> Any:
    """Three-valued: True, False, or None (NOT-CHECKED / unbound)."""
    op = ast.get("op")
    if op in {"AND", "OR"}:
        left = eval_ast(ast["left"], bindings)
        right = eval_ast(ast["right"], bindings)
        if op == "AND":
            if left is False or right is False:
                return False
            if left is None or right is None:
                return None
            return True
        if left is True or right is True:
            return True
        if left is None or right is None:
            return None
        return False
    if op == "NOT":
        inner = eval_ast(ast["arg"], bindings)
        if inner is None:
            return None
        return not inner
    ident = ast["ident"]
    if ident not in bindings:
        return None
    got = bindings[ident]
    if op == "IDENT":
        if got is None:
            return None
        if isinstance(got, bool):
            return got
        return bool(got)
    want = ast["value"]
    if op == "==":
        return got == want
    if op == "!=":
        return got != want
    if op == ">=":
        return got >= want
    if op == "<=":
        return got <= want
    if op == ">":
        return got > want
    if op == "<":
        return got < want
    raise ParseError(f"unknown op {op}")


def eval_source(src: str, bindings: dict[str, Any]) -> Any:
    return eval_ast(parse(src)["ast"], bindings)


if __name__ == "__main__":
    failed = 0
    for line, expr in SPEC_EXAMPLES:
        ok, why = accepts_unchanged(expr)
        print(f"A10 line={line} accepted={ok} why={why} expr={expr}")
        if not ok:
            failed += 1
    tautology = "x AND NOT x"
    try:
        parse(tautology)
        print(f"A10 tautology-parses={tautology!r} (static unsat rejection is CNL-0010)")
    except ParseError as exc:
        print(f"A10 tautology-parse-error:{exc}")
        failed += 1
    raise SystemExit(1 if failed else 0)
