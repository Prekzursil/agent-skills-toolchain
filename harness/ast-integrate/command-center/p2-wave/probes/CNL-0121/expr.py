#!/usr/bin/env python3
"""Recursive-descent evaluator for council stopping expressions.

Three-valued: True, False, None (NOT-CHECKED). A stop FIRES only on True.
AND of (True, None) is None, not True — that is the AND-as-OR trap.
"""
from __future__ import annotations

import re
from typing import Any

KEYWORDS = {"AND", "OR", "NOT"}
OPS = ("==", "!=", ">=", "<=", ">", "<")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")


class ParseError(ValueError):
    pass


def tokenize(source: str) -> list[tuple[str, Any]]:
    s = source.strip()
    i = 0
    out: list[tuple[str, Any]] = []
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        if s.startswith("(", i):
            out.append(("LPAREN", "("))
            i += 1
            continue
        if s.startswith(")", i):
            out.append(("RPAREN", ")"))
            i += 1
            continue
        matched_op = next((op for op in OPS if s.startswith(op, i)), None)
        if matched_op:
            out.append(("OP", matched_op))
            i += len(matched_op)
            continue
        m = NUM_RE.match(s, i)
        if m:
            raw = m.group(0)
            out.append(("NUM", float(raw) if "." in raw else int(raw)))
            i = m.end()
            continue
        m = IDENT_RE.match(s, i)
        if m:
            word = m.group(0)
            upper = word.upper()
            if upper in KEYWORDS:
                out.append((upper, upper))
            elif upper == "TRUE":
                out.append(("BOOL", True))
            elif upper == "FALSE":
                out.append(("BOOL", False))
            else:
                out.append(("IDENT", word))
            i = m.end()
            continue
        raise ParseError(f"unexpected character {s[i]!r} at {i} in {source!r}")
    out.append(("EOF", None))
    return out


class Parser:
    def __init__(self, tokens: list[tuple[str, Any]], source: str) -> None:
        self.tokens = tokens
        self.source = source
        self.i = 0

    def peek(self) -> tuple[str, Any]:
        return self.tokens[self.i]

    def eat(self, kind: str) -> Any:
        got, val = self.peek()
        if got != kind:
            raise ParseError(f"expected {kind} got {got} in {self.source!r}")
        self.i += 1
        return val

    def parse(self) -> Any:
        node = self.parse_or()
        self.eat("EOF")
        return node

    def parse_or(self) -> Any:
        left = self.parse_and()
        while self.peek()[0] == "OR":
            self.eat("OR")
            left = ("or", left, self.parse_and())
        return left

    def parse_and(self) -> Any:
        left = self.parse_not()
        while self.peek()[0] == "AND":
            self.eat("AND")
            left = ("and", left, self.parse_not())
        return left

    def parse_not(self) -> Any:
        if self.peek()[0] == "NOT":
            self.eat("NOT")
            return ("not", self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self) -> Any:
        if self.peek()[0] == "LPAREN":
            self.eat("LPAREN")
            node = self.parse_or()
            self.eat("RPAREN")
            return node
        ident = self.eat("IDENT")
        op = self.eat("OP")
        return ("cmp", ident, op, self.parse_value())

    def parse_value(self) -> Any:
        kind, val = self.peek()
        if kind == "NUM":
            self.eat("NUM")
            return val
        if kind == "BOOL":
            self.eat("BOOL")
            return val
        if kind == "IDENT":
            return self.eat("IDENT")
        raise ParseError(f"expected value got {kind} in {self.source!r}")


def parse(expression: str) -> Any:
    return Parser(tokenize(expression), expression).parse()


def _cmp(lhs: Any, op: str, rhs: Any) -> bool:
    if op in {">=", "<=", ">", "<"}:
        return {
            ">=": lhs >= rhs,
            "<=": lhs <= rhs,
            ">": lhs > rhs,
            "<": lhs < rhs,
        }[op]
    if op == "==":
        if isinstance(rhs, str) and not isinstance(lhs, str):
            return str(lhs) == rhs
        return lhs == rhs
    if op == "!=":
        if isinstance(rhs, str) and not isinstance(lhs, str):
            return str(lhs) != rhs
        return lhs != rhs
    raise ParseError(f"unknown op {op}")


def eval_ast(node: Any, metrics: dict[str, Any]) -> bool | None:
    kind = node[0]
    if kind == "and":
        a = eval_ast(node[1], metrics)
        b = eval_ast(node[2], metrics)
        if a is False or b is False:
            return False
        if a is None or b is None:
            return None
        return True
    if kind == "or":
        a = eval_ast(node[1], metrics)
        b = eval_ast(node[2], metrics)
        if a is True or b is True:
            return True
        if a is None or b is None:
            return None
        return False
    if kind == "not":
        v = eval_ast(node[1], metrics)
        if v is None:
            return None
        return not v
    if kind == "cmp":
        _, ident, op, rhs = node
        if ident not in metrics:
            return None
        return _cmp(metrics[ident], op, rhs)
    raise ParseError(f"unknown node {kind}")


def evaluate(expression: str, metrics: dict[str, Any]) -> bool | None:
    return eval_ast(parse(expression), metrics)


def observed(value: bool | None) -> str:
    if value is True:
        return "FIRE"
    if value is False:
        return "SILENT"
    return "NOT-CHECKED"


def fires(value: bool | None) -> bool:
    return value is True
