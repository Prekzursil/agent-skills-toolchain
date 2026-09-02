#!/usr/bin/env python3
"""A10 stopping-expression surface used by WFA-0046 gate conditions.

Atoms: IDENT OP VALUE with OP in {==, !=, >=, <=, >, <}.
VALUE: true, false, number, or bare identifier (PASS, APPROVED).
Connectives: AND / OR / NOT and parentheses.
Expressions are stored unchanged; parse must not rewrite the source string.
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
