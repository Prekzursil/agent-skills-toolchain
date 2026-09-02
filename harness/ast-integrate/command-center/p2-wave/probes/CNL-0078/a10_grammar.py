#!/usr/bin/env python3
"""A10 stopping-expression grammar (CNL-0010 surface, local to this unit).

Covers AND / OR / NOT, comparisons, ANY / ALL / weighted forms.
The six spec examples at _USER-PROMPTS.md:10937-10942 must parse unchanged:
the original source string is preserved on the AST and pretty() is a
normalization, not a rewrite of operators.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SPEC_EXPRESSIONS = [
    ("10937", "unique_ideas >= 100 AND completeness_score >= 0.90"),
    ("10938", "consensus >= 0.95 AND no_new_objection_rounds >= 2"),
    ("10939", "unanimity == true OR max_rounds == 12"),
    ("10940", "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0"),
    ("10941", "evidence_saturation == true OR time_minutes >= 180"),
    ("10942", "proof_of_impossibility == true"),
]

CNL_0078_EXPR = SPEC_EXPRESSIONS[0][1]

_TOKEN = re.compile(
    r"""
    \s*
    (
        AND|OR|NOT|ANY|ALL|WEIGHTED
      | >=|<=|==|!=|>|<
      | [A-Za-z_][A-Za-z0-9_]*
      | \d+\.\d+|\d+
      | [(),:]
    )
    """,
    re.VERBOSE,
)

_KEYWORDS = {"AND", "OR", "NOT", "ANY", "ALL", "WEIGHTED", "true", "false"}
_OPS = {">=", "<=", "==", "!=", ">", "<"}


class ParseError(ValueError):
    pass


@dataclass
class Node:
    kind: str
    src: str = ""
    ident: str | None = None
    op: str | None = None
    value: Any = None
    raw_value: str | None = None
    children: list["Node"] = field(default_factory=list)
    weight: float | None = None
    raw_weight: str | None = None

    def identifiers(self) -> set[str]:
        out: set[str] = set()
        if self.kind == "cmp" and self.ident:
            out.add(self.ident)
        for ch in self.children:
            out |= ch.identifiers()
        return out


def tokenize(src: str) -> list[str]:
    pos = 0
    tokens: list[str] = []
    n = len(src)
    while pos < n:
        m = _TOKEN.match(src, pos)
        if not m:
            rest = src[pos:].strip()
            if not rest:
                break
            raise ParseError(f"unrecognized token at {pos}: {rest[:20]!r}")
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = tokenize(src)
        self.i = 0

    def peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def eat(self, expected: str | None = None) -> str:
        got = self.peek()
        if got is None:
            raise ParseError("unexpected end of expression")
        if expected is not None and got != expected:
            raise ParseError(f"expected {expected!r} got {got!r}")
        self.i += 1
        return got

    def parse(self) -> Node:
        node = self.parse_or()
        if self.peek() is not None:
            raise ParseError(f"trailing token {self.peek()!r}")
        node.src = self.src
        return node

    def parse_or(self) -> Node:
        left = self.parse_and()
        while self.peek() == "OR":
            self.eat("OR")
            right = self.parse_and()
            left = Node(kind="or", children=[left, right], src=self.src)
        return left

    def parse_and(self) -> Node:
        left = self.parse_unary()
        while self.peek() == "AND":
            self.eat("AND")
            right = self.parse_unary()
            left = Node(kind="and", children=[left, right], src=self.src)
        return left

    def parse_unary(self) -> Node:
        if self.peek() == "NOT":
            self.eat("NOT")
            return Node(kind="not", children=[self.parse_unary()], src=self.src)
        return self.parse_primary()

    def parse_primary(self) -> Node:
        tok = self.peek()
        if tok == "(":
            self.eat("(")
            node = self.parse_or()
            self.eat(")")
            return node
        if tok in {"ANY", "ALL"}:
            kind = tok.lower()
            self.eat(tok)
            self.eat("(")
            children = [self.parse_or()]
            while self.peek() == ",":
                self.eat(",")
                children.append(self.parse_or())
            self.eat(")")
            return Node(kind=kind, children=children, src=self.src)
        if tok == "WEIGHTED":
            self.eat("WEIGHTED")
            self.eat("(")
            children: list[Node] = []
            while True:
                child = self.parse_or()
                self.eat(":")
                wtok = self.eat()
                try:
                    child.weight = float(wtok)
                    child.raw_weight = wtok
                except ValueError as exc:
                    raise ParseError(f"bad weight {wtok!r}") from exc
                children.append(child)
                if self.peek() == ",":
                    self.eat(",")
                    continue
                break
            self.eat(")")
            return Node(kind="weighted", children=children, src=self.src)
        return self.parse_cmp()

    def parse_cmp(self) -> Node:
        ident = self.eat()
        if ident in _OPS or ident in {"AND", "OR", "NOT", "ANY", "ALL", "WEIGHTED"}:
            raise ParseError(f"expected identifier, got {ident!r}")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", ident):
            raise ParseError(f"bad identifier {ident!r}")
        op = self.eat()
        if op not in _OPS:
            raise ParseError(f"expected comparison operator after {ident}, got {op!r}")
        raw = self.eat()
        value = _coerce_value(raw)
        return Node(
            kind="cmp", ident=ident, op=op, value=value, raw_value=raw, src=self.src
        )


def _coerce_value(raw: str) -> Any:
    if raw == "true":
        return True
    if raw == "false":
        return False
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    if re.fullmatch(r"\d+\.\d+", raw):
        return float(raw)
    return raw


def parse(src: str) -> Node:
    return _Parser(src.strip()).parse()


def pretty(node: Node) -> str:
    if node.kind == "cmp":
        rhs = node.raw_value if node.raw_value is not None else str(node.value)
        return f"{node.ident} {node.op} {rhs}"
    if node.kind == "not":
        return f"NOT {pretty(node.children[0])}"
    if node.kind == "and":
        return f"{pretty(node.children[0])} AND {pretty(node.children[1])}"
    if node.kind == "or":
        return f"{pretty(node.children[0])} OR {pretty(node.children[1])}"
    if node.kind in {"any", "all"}:
        inner = ", ".join(pretty(c) for c in node.children)
        return f"{node.kind.upper()}({inner})"
    if node.kind == "weighted":
        inner = ", ".join(
            f"{pretty(c)}: {c.raw_weight if c.raw_weight is not None else c.weight}"
            for c in node.children
        )
        return f"WEIGHTED({inner})"
    raise ParseError(f"unknown node {node.kind}")


def accepted_unchanged(src: str) -> dict[str, Any]:
    """Parse src and prove the grammar did not rewrite the expression."""
    node = parse(src)
    pretty_s = pretty(node)
    tokens_in = tokenize(src.strip())
    tokens_pretty = tokenize(pretty_s)
    return {
        "src": src,
        "accepted": True,
        "pretty": pretty_s,
        "tokens_match": tokens_in == tokens_pretty,
        "identifiers": sorted(node.identifiers()),
        "kind": node.kind,
        "src_preserved": node.src == src.strip(),
    }


def eval_node(node: Node, env: dict[str, Any]) -> bool:
    if node.kind == "cmp":
        if node.ident not in env:
            raise ParseError(f"unbound variable {node.ident}")
        left = env[node.ident]
        right = node.value
        if node.ident in {"quality_gate"} and isinstance(left, str):
            left_c, right_c = str(left), str(right)
            if node.op == "==":
                return left_c == right_c
            if node.op == "!=":
                return left_c != right_c
        if node.op == ">=":
            return left >= right
        if node.op == "<=":
            return left <= right
        if node.op == ">":
            return left > right
        if node.op == "<":
            return left < right
        if node.op == "==":
            return left == right
        if node.op == "!=":
            return left != right
        raise ParseError(f"bad op {node.op}")
    if node.kind == "and":
        return eval_node(node.children[0], env) and eval_node(node.children[1], env)
    if node.kind == "or":
        return eval_node(node.children[0], env) or eval_node(node.children[1], env)
    if node.kind == "not":
        return not eval_node(node.children[0], env)
    if node.kind == "any":
        return any(eval_node(c, env) for c in node.children)
    if node.kind == "all":
        return all(eval_node(c, env) for c in node.children)
    if node.kind == "weighted":
        num = sum((c.weight or 0.0) * (1.0 if eval_node(c, env) else 0.0) for c in node.children)
        den = sum((c.weight or 0.0) for c in node.children) or 1.0
        return (num / den) >= 0.5
    raise ParseError(f"unknown node {node.kind}")
