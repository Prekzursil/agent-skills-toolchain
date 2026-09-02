#!/usr/bin/env python3
"""A10 stopping-expression grammar (CNL-0010 surface) used unchanged by CNL-0080.

Covers AND / OR / NOT, comparisons, ANY/ALL/WEIGHTED forms. The parser stores
the input source verbatim and never rewrites it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SPEC_SIX = [
    "unique_ideas >= 100 AND completeness_score >= 0.90",
    "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    "unanimity == true OR max_rounds == 12",
    "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    "evidence_saturation == true OR time_minutes >= 180",
    "proof_of_impossibility == true",
]

CNL_0080_EXPR = SPEC_SIX[2]
SPEC_LINE = {
    SPEC_SIX[0]: 10937,
    SPEC_SIX[1]: 10938,
    SPEC_SIX[2]: 10939,
    SPEC_SIX[3]: 10940,
    SPEC_SIX[4]: 10941,
    SPEC_SIX[5]: 10942,
}

AND, OR, NOT = "AND", "OR", "NOT"
TRUE, FALSE = "true", "false"
OPS = ("==", "!=", ">=", "<=", ">", "<")


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: Any
    pos: int


@dataclass(frozen=True)
class ParseResult:
    source_verbatim: str
    ast: dict
    accepted: bool


def tokenize(src: str) -> list[Token]:
    i, n, out = 0, len(src), []
    while i < n:
        ch = src[i]
        if ch.isspace():
            i += 1
            continue
        if src.startswith("==", i) or src.startswith("!=", i) or src.startswith(">=", i) or src.startswith("<=", i):
            out.append(Token("OP", src[i : i + 2], i))
            i += 2
            continue
        if ch in "><":
            out.append(Token("OP", ch, i))
            i += 1
            continue
        if ch in "()":
            out.append(Token(ch, ch, i))
            i += 1
            continue
        if ch in ",":
            out.append(Token("COMMA", ch, i))
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            j = i + 1
            buf = []
            while j < n and src[j] != quote:
                buf.append(src[j])
                j += 1
            if j >= n:
                raise ParseError(f"unterminated string at {i}")
            out.append(Token("STRING", "".join(buf), i))
            i = j + 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i
            while j < n and (src[j].isdigit() or src[j] == "."):
                j += 1
            raw = src[i:j]
            out.append(Token("NUMBER", float(raw) if "." in raw else int(raw), i))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            if word in (AND, OR, NOT, "ANY", "ALL", "WEIGHTED"):
                out.append(Token(word, word, i))
            elif word == TRUE:
                out.append(Token("BOOL", True, i))
            elif word == FALSE:
                out.append(Token("BOOL", False, i))
            else:
                out.append(Token("IDENT", word, i))
            i = j
            continue
        raise ParseError(f"unexpected {ch!r} at {i}")
    out.append(Token("EOF", None, n))
    return out


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = tokenize(src)
        self.k = 0

    def peek(self) -> Token:
        return self.toks[self.k]

    def eat(self, kind: str | None = None) -> Token:
        tok = self.peek()
        if kind and tok.kind != kind:
            raise ParseError(f"expected {kind} got {tok.kind} at {tok.pos}")
        self.k += 1
        return tok

    def parse(self) -> dict:
        node = self.parse_or()
        if self.peek().kind != "EOF":
            raise ParseError(f"trailing input at {self.peek().pos}")
        return node

    def parse_or(self) -> dict:
        left = self.parse_and()
        while self.peek().kind == OR:
            self.eat(OR)
            right = self.parse_and()
            left = {"op": "OR", "args": [left, right]}
        return left

    def parse_and(self) -> dict:
        left = self.parse_not()
        while self.peek().kind == AND:
            self.eat(AND)
            right = self.parse_not()
            left = {"op": "AND", "args": [left, right]}
        return left

    def parse_not(self) -> dict:
        if self.peek().kind == NOT:
            self.eat(NOT)
            return {"op": "NOT", "arg": self.parse_not()}
        return self.parse_primary()

    def parse_primary(self) -> dict:
        tok = self.peek()
        if tok.kind == "(":
            self.eat("(")
            node = self.parse_or()
            self.eat(")")
            return node
        if tok.kind in ("ANY", "ALL"):
            kind = self.eat().kind
            self.eat("(")
            args = [self.parse_or()]
            while self.peek().kind == "COMMA":
                self.eat("COMMA")
                args.append(self.parse_or())
            self.eat(")")
            return {"op": kind, "args": args}
        if tok.kind == "WEIGHTED":
            self.eat("WEIGHTED")
            self.eat("(")
            pairs = []
            while True:
                w = self.eat("NUMBER").value
                if self.peek().kind == "COMMA":
                    self.eat("COMMA")
                expr = self.parse_or()
                pairs.append({"weight": w, "expr": expr})
                if self.peek().kind == "COMMA":
                    self.eat("COMMA")
                    continue
                break
            self.eat(")")
            return {"op": "WEIGHTED", "args": pairs}
        return self.parse_comparison()

    def parse_comparison(self) -> dict:
        left = self.eat("IDENT")
        op = self.eat("OP")
        right_tok = self.peek()
        if right_tok.kind in ("BOOL", "NUMBER", "STRING", "IDENT"):
            right = self.eat().value
        else:
            raise ParseError(f"expected value at {right_tok.pos}")
        return {
            "op": "CMP",
            "cmp": op.value,
            "left": left.value,
            "right": right,
        }


def parse(src: str) -> ParseResult:
    ast = Parser(src).parse()
    return ParseResult(source_verbatim=src, ast=ast, accepted=True)


def parse_unchanged(src: str) -> ParseResult:
    first = parse(src)
    second = parse(first.source_verbatim)
    if first.source_verbatim != src:
        raise ParseError("parser rewrote source")
    if first.ast != second.ast:
        raise ParseError("reparse AST mismatch")
    if first.source_verbatim != second.source_verbatim:
        raise ParseError("reparse rewrote source")
    return first


def static_reject_tautology(ast: dict, bindings_are_constants: dict[str, Any] | None = None) -> str | None:
    """CNL-0010: always-true comparison of a constant binding to a literal is a tautology."""
    bindings_are_constants = bindings_are_constants or {}

    def walk(node: dict) -> str | None:
        op = node.get("op")
        if op == "CMP":
            name = node["left"]
            if name in bindings_are_constants and node["cmp"] == "==":
                if bindings_are_constants[name] == node["right"]:
                    return (
                        f"tautology: {name} is bound to constant "
                        f"{bindings_are_constants[name]!r} compared == {node['right']!r}"
                    )
            return None
        if op in ("OR", "AND", "ANY", "ALL"):
            for arg in node.get("args") or []:
                hit = walk(arg)
                if hit:
                    return hit
        if op == "NOT":
            return walk(node["arg"])
        if op == "WEIGHTED":
            for arg in node.get("args") or []:
                hit = walk(arg["expr"])
                if hit:
                    return hit
        return None

    return walk(ast)
