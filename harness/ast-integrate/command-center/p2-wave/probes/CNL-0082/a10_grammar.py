#!/usr/bin/env python3
"""A10 stopping-expression grammar (AND / OR / NOT + comparisons).

CNL-0010 owns the eventual CouncilSpec v2 grammar artifact; this probe-local
parser is the A10 grammar used to prove the spec example is accepted *unchanged*
— the source string is tokenized as written, not rewritten into ANY/ALL/weighted
form before parse.
"""
from __future__ import annotations

import re
from typing import Any

SPEC_EXPR = "evidence_saturation == true OR time_minutes >= 180"

# Six required executable examples, catalog-quoted at spec 10937-10942.
# Line binding for THIS unit: _USER-PROMPTS.md:10941 == SPEC_EXPR.
SIX_SPEC_EXAMPLES: tuple[str, ...] = (
    "unique_ideas >= 100 AND completeness_score >= 0.90",
    "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    "unanimity == true OR max_rounds == 12",
    "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    SPEC_EXPR,
    "proof_of_impossibility == true",
)

_TOKEN = re.compile(
    r"""
    (?P<OR>\bOR\b)
    |(?P<AND>\bAND\b)
    |(?P<NOT>\bNOT\b)
    |(?P<TRUE>\btrue\b)
    |(?P<FALSE>\bfalse\b)
    |(?P<OP>==|!=|>=|<=|>|<)
    |(?P<NUM>\d+(?:\.\d+)?)
    |(?P<ID>[A-Za-z_][A-Za-z0-9_]*)
    |(?P<LP>\()
    |(?P<RP>\))
    |(?P<WS>[ \t]+)
    |(?P<BAD>.)
    """,
    re.VERBOSE,
)


class ParseError(ValueError):
    pass


def tokenize(src: str) -> list[tuple[str, Any]]:
    tokens: list[tuple[str, Any]] = []
    for m in _TOKEN.finditer(src):
        kind = m.lastgroup
        if kind in (None, "WS"):
            continue
        if kind == "BAD":
            raise ParseError(f"unexpected {m.group()!r} in {src!r}")
        raw = m.group()
        if kind == "NUM":
            val: Any = float(raw) if "." in raw else int(raw)
        elif kind == "TRUE":
            val = True
        elif kind == "FALSE":
            val = False
        else:
            val = raw
        tokens.append((kind, val))
    return tokens


class _Parser:
    def __init__(self, src: str) -> None:
        self.src = src
        self.tokens = tokenize(src)
        self.i = 0

    def peek(self) -> tuple[str, Any] | None:
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def eat(self, kind: str | None = None) -> tuple[str, Any]:
        tok = self.peek()
        if tok is None:
            raise ParseError(f"unexpected end of expression: {self.src!r}")
        if kind is not None and tok[0] != kind:
            raise ParseError(f"expected {kind} got {tok} in {self.src!r}")
        self.i += 1
        return tok

    def parse(self) -> dict[str, Any]:
        node = self.or_expr()
        if self.peek() is not None:
            raise ParseError(f"trailing tokens {self.tokens[self.i:]}")
        return node

    def or_expr(self) -> dict[str, Any]:
        left = self.and_expr()
        while self.peek() and self.peek()[0] == "OR":
            self.eat("OR")
            left = {"op": "OR", "left": left, "right": self.and_expr()}
        return left

    def and_expr(self) -> dict[str, Any]:
        left = self.unary()
        while self.peek() and self.peek()[0] == "AND":
            self.eat("AND")
            left = {"op": "AND", "left": left, "right": self.unary()}
        return left

    def unary(self) -> dict[str, Any]:
        if self.peek() and self.peek()[0] == "NOT":
            self.eat("NOT")
            return {"op": "NOT", "arg": self.unary()}
        return self.primary()

    def primary(self) -> dict[str, Any]:
        tok = self.peek()
        if tok is None:
            raise ParseError("expected primary")
        if tok[0] == "LP":
            self.eat("LP")
            node = self.or_expr()
            self.eat("RP")
            return node
        return self.comparison()

    def comparison(self) -> dict[str, Any]:
        ident = self.eat("ID")[1]
        op = self.eat("OP")[1]
        rhs_kind, rhs_val = self.eat()
        if rhs_kind not in {"TRUE", "FALSE", "NUM", "ID"}:
            raise ParseError(f"bad rhs {rhs_kind}")
        return {"op": op, "left": ident, "right": rhs_val}


def parse(src: str) -> dict[str, Any]:
    return _Parser(src).parse()


def accepted_unchanged(src: str) -> dict[str, Any]:
    """Parse `src` with no rewrite. Caller must pass the spec string verbatim."""
    return parse(src)


def parse_all_six() -> list[dict[str, Any]]:
    return [{"source": s, "ast": parse(s)} for s in SIX_SPEC_EXAMPLES]
