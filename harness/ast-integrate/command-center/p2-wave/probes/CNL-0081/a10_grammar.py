#!/usr/bin/env python3
"""A10 stopping-expression grammar (CNL-0010 surface, local to this unit).

A10 is the catalog name for CNL-0010 (Stopping-expression grammar and STATIC
validation). CNL-0010 is not delivered on this worktree; this module is the
grammar CNL-0081's parse test binds to. It accepts the six spec-named example
shapes. Evaluation of metrics other than this unit's expression is out of
scope.

Precedence: NOT > AND > OR. Comparisons bind tighter than unary NOT.
The source string is kept on the AST; a successful parse does not rewrite
the expression into a different operator shape.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

KEYWORDS = {"AND", "OR", "NOT", "true", "false"}
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")

# Six spec-named examples (catalog titles CNL-0078..CNL-0083 / spec 10937-10942).
# Parse-only for the five that are not this unit's evaluation target.
SPEC_SIX = (
    "unique_ideas >= 100 AND completeness_score >= 0.90",
    "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    "unanimity == true OR max_rounds == 12",
    "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    "evidence_saturation == true OR time_minutes >= 180",
    "proof_of_impossibility == true",
)

THIS_EXPRESSION = SPEC_SIX[3]


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: Any
    src: str


@dataclass(frozen=True)
class Node:
    kind: str
    source_text: str
    left: Any = None
    op: str | None = None
    right: Any = None
    name: str | None = None
    value: Any = None
    inner: Any = None


def tokenize(text: str) -> list[Token]:
    i, n = 0, len(text)
    out: list[Token] = []
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("==", i):
            out.append(Token("OP", "==", "=="))
            i += 2
            continue
        if text.startswith("!=", i):
            out.append(Token("OP", "!=", "!="))
            i += 2
            continue
        if text.startswith(">=", i):
            out.append(Token("OP", ">=", ">="))
            i += 2
            continue
        if text.startswith("<=", i):
            out.append(Token("OP", "<=", "<="))
            i += 2
            continue
        if ch in "><":
            out.append(Token("OP", ch, ch))
            i += 1
            continue
        if ch == "(":
            out.append(Token("LPAREN", "(", "("))
            i += 1
            continue
        if ch == ")":
            out.append(Token("RPAREN", ")", ")"))
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            j = i + 1
            buf = []
            while j < n and text[j] != quote:
                buf.append(text[j])
                j += 1
            if j >= n:
                raise ParseError("unterminated string")
            s = "".join(buf)
            out.append(Token("STRING", s, text[i : j + 1]))
            i = j + 1
            continue
        m = NUMBER_RE.match(text, i)
        if m and (i == 0 or not text[i - 1].isalpha()):
            raw = m.group(0)
            if "." in raw:
                out.append(Token("NUMBER", float(raw), raw))
            else:
                out.append(Token("NUMBER", int(raw), raw))
            i = m.end()
            continue
        m = IDENT_RE.match(text, i)
        if m:
            raw = m.group(0)
            if raw in ("AND", "OR", "NOT"):
                out.append(Token(raw, raw, raw))
            elif raw in ("true", "false"):
                out.append(Token("BOOL", raw == "true", raw))
            else:
                out.append(Token("IDENT", raw, raw))
            i = m.end()
            continue
        raise ParseError(f"unexpected character {ch!r} at {i}")
    out.append(Token("EOF", None, ""))
    return out


class Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens = tokenize(text)
        self.i = 0

    def peek(self) -> Token:
        return self.tokens[self.i]

    def eat(self, kind: str | None = None) -> Token:
        tok = self.peek()
        if kind is not None and tok.kind != kind:
            raise ParseError(f"expected {kind}, got {tok.kind} ({tok.src!r})")
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.parse_or()
        if self.peek().kind != "EOF":
            raise ParseError(f"trailing input {self.peek().src!r}")
        return Node(
            kind=node.kind,
            source_text=self.text,
            left=node.left,
            op=node.op,
            right=node.right,
            name=node.name,
            value=node.value,
            inner=node.inner,
        )

    def parse_or(self) -> Node:
        left = self.parse_and()
        while self.peek().kind == "OR":
            self.eat("OR")
            right = self.parse_and()
            left = Node(kind="OR", source_text=self.text, left=left, op="OR", right=right)
        return left

    def parse_and(self) -> Node:
        left = self.parse_unary()
        while self.peek().kind == "AND":
            self.eat("AND")
            right = self.parse_unary()
            left = Node(kind="AND", source_text=self.text, left=left, op="AND", right=right)
        return left

    def parse_unary(self) -> Node:
        if self.peek().kind == "NOT":
            self.eat("NOT")
            inner = self.parse_unary()
            return Node(kind="NOT", source_text=self.text, op="NOT", inner=inner)
        return self.parse_cmp()

    def parse_cmp(self) -> Node:
        if self.peek().kind == "LPAREN":
            self.eat("LPAREN")
            inner = self.parse_or()
            self.eat("RPAREN")
            return Node(kind="PAREN", source_text=self.text, inner=inner)
        left = self.parse_atom()
        if self.peek().kind == "OP":
            op = self.eat("OP").value
            right = self.parse_atom()
            return Node(kind="CMP", source_text=self.text, left=left, op=op, right=right)
        return left

    def parse_atom(self) -> Node:
        tok = self.peek()
        if tok.kind == "IDENT":
            self.eat("IDENT")
            return Node(kind="IDENT", source_text=tok.src, name=tok.value)
        if tok.kind == "NUMBER":
            self.eat("NUMBER")
            return Node(kind="NUMBER", source_text=tok.src, value=tok.value)
        if tok.kind == "STRING":
            self.eat("STRING")
            return Node(kind="STRING", source_text=tok.src, value=tok.value)
        if tok.kind == "BOOL":
            self.eat("BOOL")
            return Node(kind="BOOL", source_text=tok.src, value=tok.value)
        raise ParseError(f"expected atom, got {tok.kind} ({tok.src!r})")


def parse(text: str) -> Node:
    return Parser(text).parse()


def accepted_unchanged(text: str) -> Node:
    """Parse and prove the grammar did not rewrite the source string."""
    node = parse(text)
    if node.source_text != text:
        raise ParseError("parser rewrote source_text")
    return node


def _literal(node: Node) -> Any:
    if node.kind in ("NUMBER", "STRING", "BOOL"):
        return node.value
    if node.kind == "IDENT":
        return node.name
    raise ParseError(f"not a literal: {node.kind}")


def _lookup(node: Node, env: dict[str, Any]) -> Any:
    if node.kind == "IDENT":
        if node.name in env:
            return env[node.name]
        return node.name  # enum / bare identifier (PASS, FAIL, …)
    if node.kind in ("NUMBER", "STRING", "BOOL"):
        return node.value
    raise ParseError(f"cannot evaluate atom {node.kind}")


def _cmp(op: str, left: Any, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    raise ParseError(f"unknown op {op}")


def eval_node(node: Node, env: dict[str, Any]) -> bool:
    if node.kind == "AND":
        return bool(eval_node(node.left, env) and eval_node(node.right, env))
    if node.kind == "OR":
        return bool(eval_node(node.left, env) or eval_node(node.right, env))
    if node.kind == "NOT":
        return not bool(eval_node(node.inner, env))
    if node.kind == "PAREN":
        return bool(eval_node(node.inner, env))
    if node.kind == "CMP":
        return _cmp(node.op or "", _lookup(node.left, env), _lookup(node.right, env))
    if node.kind == "BOOL":
        return bool(node.value)
    if node.kind == "IDENT":
        return bool(_lookup(node, env))
    raise ParseError(f"cannot evaluate {node.kind}")


def eval_source(text: str, env: dict[str, Any]) -> bool:
    return eval_node(accepted_unchanged(text), env)
