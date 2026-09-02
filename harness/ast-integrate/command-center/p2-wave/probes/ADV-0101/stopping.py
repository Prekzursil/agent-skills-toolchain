#!/usr/bin/env python3
"""Composable AND/OR/NOT stopping-expression parser and three-valued evaluator.

Missing metrics evaluate to NOT-CHECKED. AND is never treated as OR under
partial evidence: TRUE AND NOT-CHECKED is NOT-CHECKED, not TRUE.
"""
from __future__ import annotations

import re
from typing import Any

TV_TRUE = "TRUE"
TV_FALSE = "FALSE"
TV_UNCHECKED = "NOT-CHECKED"

AND = "AND"
OR = "OR"
NOT = "NOT"

TOKEN_RE = re.compile(
    r"""
    \s*
    (
        >=|<=|==|!=|>|<
        |\bAND\b|\bOR\b|\bNOT\b
        |\btrue\b|\bfalse\b
        |[A-Za-z_][A-Za-z0-9_]*
        |\d+(?:\.\d+)?
        |"(?:[^"\\]|\\.)*"
        |'(?:[^'\\]|\\.)*'
        |\(|\)
    )
    """,
    re.VERBOSE,
)

# Spec examples at _USER-PROMPTS.md:10937-10942 (catalog CNL-0078..CNL-0083).
SPEC_EXPRESSIONS: list[dict[str, str]] = [
    {
        "id": "E1",
        "spec_lines": "10937",
        "text": "unique_ideas >= 100 AND completeness_score >= 0.90",
        "title": "unique_ideas >= 100 AND completeness_score >= 0.90",
    },
    {
        "id": "E2",
        "spec_lines": "10938",
        "text": "consensus >= 0.95 AND no_new_objection_rounds >= 2",
        "title": "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    },
    {
        "id": "E3",
        "spec_lines": "10939",
        "text": "unanimity == true OR max_rounds == 12",
        "title": "unanimity == true OR max_rounds == 12",
    },
    {
        "id": "E4",
        "spec_lines": "10940",
        "text": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
        "title": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    },
    {
        "id": "E5",
        "spec_lines": "10941",
        "text": "evidence_saturation == true OR time_minutes >= 180",
        "title": "evidence_saturation == true OR time_minutes >= 180",
    },
    {
        "id": "E6",
        "spec_lines": "10942",
        "text": "proof_of_impossibility == true",
        "title": "proof_of_impossibility == true",
    },
]


class ParseError(ValueError):
    pass


def tokenize(text: str) -> list[tuple[str, Any]]:
    pos = 0
    out: list[tuple[str, Any]] = []
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ParseError(f"unrecognized token at {pos}: {text[pos:pos + 20]!r}")
        raw = m.group(1)
        pos = m.end()
        if raw in {AND, OR, NOT}:
            out.append((raw, raw))
        elif raw in {">=", "<=", "==", "!=", ">", "<"}:
            out.append(("OP", raw))
        elif raw == "(":
            out.append(("LP", raw))
        elif raw == ")":
            out.append(("RP", raw))
        elif raw.lower() == "true":
            out.append(("BOOL", True))
        elif raw.lower() == "false":
            out.append(("BOOL", False))
        elif raw[0] in "\"'":
            out.append(("STR", raw[1:-1]))
        elif re.fullmatch(r"\d+(?:\.\d+)?", raw):
            out.append(("NUM", float(raw) if "." in raw else int(raw)))
        else:
            out.append(("ID", raw))
    out.append(("EOF", None))
    return out


class Parser:
    def __init__(self, tokens: list[tuple[str, Any]]):
        self.tokens = tokens
        self.i = 0

    def peek(self) -> tuple[str, Any]:
        return self.tokens[self.i]

    def eat(self, kind: str | None = None) -> tuple[str, Any]:
        tok = self.tokens[self.i]
        if kind is not None and tok[0] != kind:
            raise ParseError(f"expected {kind} got {tok}")
        self.i += 1
        return tok

    def parse(self) -> dict:
        node = self.parse_or()
        if self.peek()[0] != "EOF":
            raise ParseError(f"trailing tokens {self.peek()}")
        return node

    def parse_or(self) -> dict:
        left = self.parse_and()
        while self.peek()[0] == OR:
            self.eat(OR)
            left = {"op": OR, "args": [left, self.parse_and()]}
        return left

    def parse_and(self) -> dict:
        left = self.parse_not()
        while self.peek()[0] == AND:
            self.eat(AND)
            left = {"op": AND, "args": [left, self.parse_not()]}
        return left

    def parse_not(self) -> dict:
        if self.peek()[0] == NOT:
            self.eat(NOT)
            return {"op": NOT, "args": [self.parse_not()]}
        return self.parse_cmp()

    def parse_cmp(self) -> dict:
        left = self.parse_primary()
        if self.peek()[0] == "OP":
            op = self.eat("OP")[1]
            right = self.parse_primary()
            return {"op": op, "args": [left, right]}
        return left

    def parse_primary(self) -> dict:
        kind, val = self.peek()
        if kind == "LP":
            self.eat("LP")
            node = self.parse_or()
            self.eat("RP")
            return node
        if kind == "ID":
            self.eat("ID")
            if val in {"PASS", "FAIL", "TRUE", "FALSE"}:
                mapped: Any = {
                    "PASS": "PASS",
                    "FAIL": "FAIL",
                    "TRUE": True,
                    "FALSE": False,
                }[val]
                return {"op": "lit", "value": mapped}
            return {"op": "var", "name": val}
        if kind == "NUM":
            self.eat("NUM")
            return {"op": "lit", "value": val}
        if kind == "STR":
            self.eat("STR")
            return {"op": "lit", "value": val}
        if kind == "BOOL":
            self.eat("BOOL")
            return {"op": "lit", "value": val}
        raise ParseError(f"expected primary, got {(kind, val)}")


def parse(text: str) -> dict:
    return Parser(tokenize(text)).parse()


def _tv_and(a: str, b: str) -> str:
    if a == TV_FALSE or b == TV_FALSE:
        return TV_FALSE
    if a == TV_TRUE and b == TV_TRUE:
        return TV_TRUE
    return TV_UNCHECKED


def _tv_or(a: str, b: str) -> str:
    if a == TV_TRUE or b == TV_TRUE:
        return TV_TRUE
    if a == TV_FALSE and b == TV_FALSE:
        return TV_FALSE
    return TV_UNCHECKED


def _tv_not(a: str) -> str:
    if a == TV_TRUE:
        return TV_FALSE
    if a == TV_FALSE:
        return TV_TRUE
    return TV_UNCHECKED


def _coerce_lit(val: Any) -> Any:
    return val


def _lookup(name: str, bindings: dict[str, Any]) -> tuple[str, Any]:
    if name not in bindings or bindings[name] is None:
        return TV_UNCHECKED, None
    return TV_TRUE, bindings[name]


def _cmp(op: str, left: Any, right: Any) -> str:
    if op == "==":
        if isinstance(right, bool) or isinstance(left, bool):
            return TV_TRUE if bool(left) is bool(right) else TV_FALSE
        if isinstance(right, str) or isinstance(left, str):
            return TV_TRUE if str(left) == str(right) else TV_FALSE
        return TV_TRUE if left == right else TV_FALSE
    if op == "!=":
        inv = _cmp("==", left, right)
        return TV_FALSE if inv == TV_TRUE else TV_TRUE
    try:
        lf, rf = float(left), float(right)
    except (TypeError, ValueError):
        return TV_UNCHECKED
    ok = {
        ">=": lf >= rf,
        "<=": lf <= rf,
        ">": lf > rf,
        "<": lf < rf,
    }.get(op)
    if ok is None:
        return TV_UNCHECKED
    return TV_TRUE if ok else TV_FALSE


def eval_tree(node: dict, bindings: dict[str, Any]) -> str:
    op = node["op"]
    if op == "var":
        tv, _ = _lookup(node["name"], bindings)
        if tv == TV_UNCHECKED:
            return TV_UNCHECKED
        val = bindings[node["name"]]
        if isinstance(val, bool):
            return TV_TRUE if val else TV_FALSE
        return TV_TRUE
    if op == "lit":
        val = node["value"]
        if isinstance(val, bool):
            return TV_TRUE if val else TV_FALSE
        return TV_TRUE
    if op == AND:
        return _tv_and(eval_tree(node["args"][0], bindings), eval_tree(node["args"][1], bindings))
    if op == OR:
        return _tv_or(eval_tree(node["args"][0], bindings), eval_tree(node["args"][1], bindings))
    if op == NOT:
        return _tv_not(eval_tree(node["args"][0], bindings))
    left, right = node["args"]
    if left["op"] == "var":
        tv, lval = _lookup(left["name"], bindings)
        if tv == TV_UNCHECKED:
            return TV_UNCHECKED
    elif left["op"] == "lit":
        lval = _coerce_lit(left["value"])
    else:
        return TV_UNCHECKED
    if right["op"] == "var":
        tv, rval = _lookup(right["name"], bindings)
        if tv == TV_UNCHECKED:
            return TV_UNCHECKED
    elif right["op"] == "lit":
        rval = _coerce_lit(right["value"])
    else:
        return TV_UNCHECKED
    return _cmp(op, lval, rval)


def evaluate(text: str, bindings: dict[str, Any]) -> dict[str, Any]:
    tree = parse(text)
    tv = eval_tree(tree, bindings)
    return {
        "expression": text,
        "value": tv,
        "tv": tv,
        "stop": tv == TV_TRUE,
        "tree": tree,
    }


def and_is_not_or_under_partial() -> dict[str, Any]:
    """Control: unique_ideas met, completeness missing => AND is NOT-CHECKED, not TRUE."""
    expr = "unique_ideas >= 100 AND completeness_score >= 0.90"
    partial = evaluate(expr, {"unique_ideas": 100})
    both = evaluate(expr, {"unique_ideas": 100, "completeness_score": 0.90})
    none = evaluate(expr, {"unique_ideas": 1, "completeness_score": 0.1})
    or_partial = evaluate(
        "unique_ideas >= 100 OR completeness_score >= 0.90",
        {"unique_ideas": 100},
    )
    return {
        "id": "NC-AND-NOT-OR-PARTIAL",
        "partial_and": partial["value"],
        "partial_and_would_be_true_if_or": or_partial["value"],
        "both_true": both["value"],
        "both_false": none["value"],
        "and_did_not_behave_as_or": partial["value"] == TV_UNCHECKED
        and or_partial["value"] == TV_TRUE,
        "fired_on_bad_state": partial["value"] == TV_UNCHECKED,
        "silent_on_good_state": both["value"] == TV_TRUE and none["value"] == TV_FALSE,
    }
