"""Composable stopping expressions for CouncilSpec: parse, unparse, evaluate.

Three capabilities, all typed against the metric registry in the schema:

* ``parse(text)``      - the human form (``unique_ideas >= 100 AND completeness_score >= 0.90``)
                         into the canonical JSON tree the schema validates.
* ``unparse(tree)``    - canonical tree back to a string (round-trips at TREE level; it does
                         NOT promise byte-identical text, because ``0.90`` normalises to ``0.9``).
* ``evaluate(tree, m)``- execute the tree against a metric snapshot. Strict: an unknown or
                         wrongly-typed metric value raises rather than silently reading false.

Grammar (NOT binds tighter than AND, which binds tighter than OR):

    expr    := or_expr
    or_expr := and_expr (OR and_expr)*
    and_expr:= unary (AND unary)*
    unary   := NOT unary | primary
    primary := "(" expr ")" | nary | leaf
    nary    := ("ANY" | "ALL") "[" expr ("," expr)* "]"
    leaf    := IDENT OP VALUE

``ANY[a, b]`` / ``ALL[a, b]`` is the surface form used by the preset catalogue and named at
spec line 10760 ("composable stopping rules with ANY, ALL, and weighted logic"); it is INPUT
SUGAR that normalises to ``any_of`` / ``all_of``. ``unparse`` always emits the AND/OR form
(one canonical output), so the round trip is tree-level, not text-level.
    IDENT   := [a-z][a-z0-9_]*  |  custom:[a-z][a-z0-9_]*
    OP      := ">=" | "<=" | "!=" | "==" | ">" | "<"
    VALUE   := number | true | false | ENUM_TOKEN([A-Z][A-Z0-9_]*)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .registry import (
    CUSTOM_PREFIX,
    domain_of,
    enum_tokens,
    legal_ops,
)

__all__ = [
    "ExpressionError",
    "MissingMetricError",
    "MetricTypeError",
    "parse",
    "unparse",
    "evaluate",
    "iter_leaves",
    "referenced_metrics",
]


class ExpressionError(ValueError):
    """Malformed or ill-typed stopping expression."""


class MissingMetricError(KeyError):
    """A metric referenced by the expression was absent from the snapshot."""


class MetricTypeError(TypeError):
    """A metric snapshot value had the wrong Python type for its declared domain."""


# --------------------------------------------------------------------------- lexer

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<lparen>\()
  | (?P<rparen>\))
  | (?P<lbracket>\[)
  | (?P<rbracket>\])
  | (?P<comma>,)
  | (?P<op>>=|<=|!=|==|>|<)
  | (?P<number>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
  | (?P<kw>\b(?:AND|OR|NOT)\b)
  | (?P<enum>\b[A-Z][A-Z0-9_]*\b)
  | (?P<ident>\b(?:custom:)?[a-z][a-z0-9_]*\b)
    """,
    re.VERBOSE,
)

_BOOL_LITERALS = {"true": True, "false": False}


def _lex(text: str) -> List[Tuple[str, str, int]]:
    tokens: List[Tuple[str, str, int]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ExpressionError(f"unexpected character {text[pos]!r} at offset {pos}")
        kind = m.lastgroup
        assert kind is not None
        if kind != "ws":
            tokens.append((kind, m.group(), pos))
        pos = m.end()
    return tokens


# -------------------------------------------------------------------------- parser


class _Parser:
    def __init__(self, tokens: Sequence[Tuple[str, str, int]], text: str) -> None:
        self.tokens = list(tokens)
        self.i = 0
        self.text = text

    def peek(self) -> Tuple[str, str, int] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def next(self) -> Tuple[str, str, int]:
        tok = self.peek()
        if tok is None:
            raise ExpressionError(f"unexpected end of expression: {self.text!r}")
        self.i += 1
        return tok

    def expect(self, kind: str, value: str | None = None) -> Tuple[str, str, int]:
        tok = self.next()
        if tok[0] != kind or (value is not None and tok[1] != value):
            raise ExpressionError(
                f"expected {value or kind} at offset {tok[2]}, found {tok[1]!r}"
            )
        return tok

    def at_keyword(self, word: str) -> bool:
        tok = self.peek()
        return tok is not None and tok[0] == "kw" and tok[1] == word

    # or_expr := and_expr (OR and_expr)*
    def parse_or(self) -> Dict[str, Any]:
        parts = [self.parse_and()]
        while self.at_keyword("OR"):
            self.next()
            parts.append(self.parse_and())
        return parts[0] if len(parts) == 1 else {"any_of": parts}

    # and_expr := unary (AND unary)*
    def parse_and(self) -> Dict[str, Any]:
        parts = [self.parse_unary()]
        while self.at_keyword("AND"):
            self.next()
            parts.append(self.parse_unary())
        return parts[0] if len(parts) == 1 else {"all_of": parts}

    # unary := NOT unary | primary
    def parse_unary(self) -> Dict[str, Any]:
        if self.at_keyword("NOT"):
            self.next()
            return {"not": self.parse_unary()}
        return self.parse_primary()

    # primary := "(" expr ")" | nary | leaf
    def parse_primary(self) -> Dict[str, Any]:
        tok = self.peek()
        if tok is None:
            raise ExpressionError(f"unexpected end of expression: {self.text!r}")
        if tok[0] == "lparen":
            self.next()
            inner = self.parse_or()
            self.expect("rparen")
            return inner
        if tok[0] == "enum" and tok[1] in ("ANY", "ALL"):
            nxt = self.tokens[self.i + 1] if self.i + 1 < len(self.tokens) else None
            if nxt is not None and nxt[0] == "lbracket":
                return self.parse_nary()
        return self.parse_leaf()

    # nary := ("ANY"|"ALL") "[" expr ("," expr)* "]"
    def parse_nary(self) -> Dict[str, Any]:
        _, word, offset = self.next()
        self.expect("lbracket")
        operands = [self.parse_or()]
        while self.peek() is not None and self.peek()[0] == "comma":
            self.next()
            operands.append(self.parse_or())
        self.expect("rbracket")
        if len(operands) < 2:
            raise ExpressionError(
                f"{word}[...] at offset {offset} needs at least two operands; a one-operand "
                f"{word} is the operand itself"
            )
        return {"any_of" if word == "ANY" else "all_of": operands}

    def parse_leaf(self) -> Dict[str, Any]:
        kind, ident, offset = self.next()
        if kind == "ident" and ident in _BOOL_LITERALS:
            raise ExpressionError(
                f"bare boolean literal {ident!r} at offset {offset}; write "
                f"<metric> == {ident} instead"
            )
        if kind != "ident":
            raise ExpressionError(f"expected a metric name at offset {offset}, found {ident!r}")
        try:
            domain = domain_of(ident)
        except KeyError:
            raise ExpressionError(
                f"unknown metric {ident!r} at offset {offset}; not in the schema registry "
                f"(use a custom:<name> metric with a declared value_type for extensions)"
            ) from None

        _, op, op_off = self.expect("op")
        allowed = legal_ops(domain)
        if op not in allowed:
            raise ExpressionError(
                f"operator {op!r} at offset {op_off} is illegal for {domain} metric "
                f"{ident!r}; legal: {list(allowed)}"
            )

        vkind, vtext, voff = self.next()
        leaf: Dict[str, Any] = {"metric": ident, "op": op}

        if domain == "numeric":
            if vkind != "number":
                raise ExpressionError(
                    f"numeric metric {ident!r} needs a number at offset {voff}, found {vtext!r}"
                )
            leaf["value"] = _num(vtext)
        elif domain == "boolean":
            if vkind != "ident" or vtext not in _BOOL_LITERALS:
                raise ExpressionError(
                    f"boolean metric {ident!r} needs true/false at offset {voff}, found {vtext!r}"
                )
            leaf["value"] = _BOOL_LITERALS[vtext]
        elif domain == "enum":
            if vkind not in ("enum", "kw") or vtext not in enum_tokens():
                raise ExpressionError(
                    f"enum metric {ident!r} needs one of the schema enum tokens at offset "
                    f"{voff}, found {vtext!r}"
                )
            leaf["value"] = vtext
        else:  # custom
            if vkind == "number":
                leaf["value"] = _num(vtext)
                leaf["value_type"] = "number"
            elif vkind == "ident" and vtext in _BOOL_LITERALS:
                leaf["value"] = _BOOL_LITERALS[vtext]
                leaf["value_type"] = "boolean"
            elif vkind in ("enum", "kw"):
                leaf["value"] = vtext
                leaf["value_type"] = "string"
            else:
                raise ExpressionError(
                    f"custom metric {ident!r} has an unusable value at offset {voff}: {vtext!r}"
                )
            if leaf["value_type"] != "number" and op not in ("==", "!="):
                raise ExpressionError(
                    f"custom metric {ident!r} with a {leaf['value_type']} value may only use "
                    f"== or !=, not {op!r}"
                )
        return leaf


def _num(text: str) -> float | int:
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return float(text)


def parse(text: str) -> Dict[str, Any]:
    """Parse the human stopping-rule form into the canonical schema tree."""
    if not isinstance(text, str) or not text.strip():
        raise ExpressionError("empty stopping expression")
    parser = _Parser(_lex(text), text)
    tree = parser.parse_or()
    leftover = parser.peek()
    if leftover is not None:
        raise ExpressionError(f"trailing token {leftover[1]!r} at offset {leftover[2]}")
    return tree


# ------------------------------------------------------------------------ unparser

_PREC = {"leaf": 3, "not": 2, "all_of": 1, "any_of": 0, "weighted": 3}


def _node_kind(node: Mapping[str, Any]) -> str:
    for key in ("all_of", "any_of", "not", "weighted"):
        if key in node:
            return key
    if "metric" in node:
        return "leaf"
    raise ExpressionError(f"unrecognised expression node: {sorted(node)}")


def _fmt_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def unparse(node: Mapping[str, Any]) -> str:
    """Canonical string form. Round-trips at TREE level, not byte level."""
    kind = _node_kind(node)
    if kind == "leaf":
        return f"{node['metric']} {node['op']} {_fmt_value(node['value'])}"
    if kind == "not":
        inner = node["not"]
        body = unparse(inner)
        if _PREC[_node_kind(inner)] < _PREC["not"]:
            body = f"({body})"
        return f"NOT {body}"
    if kind == "weighted":
        spec = node["weighted"]
        clauses = ", ".join(
            f"{c['weight']}*({unparse(c['when'])})" for c in spec["clauses"]
        )
        return f"WEIGHTED[{clauses}] >= {spec['threshold']}"
    joiner = " AND " if kind == "all_of" else " OR "
    parts = []
    for child in node[kind]:
        body = unparse(child)
        if _PREC[_node_kind(child)] < _PREC[kind]:
            body = f"({body})"
        parts.append(body)
    return joiner.join(parts)


# ----------------------------------------------------------------------- evaluator

_COMPARATORS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _check_snapshot_type(metric: str, domain: str, value: Any, declared: str | None) -> None:
    if domain == "numeric":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MetricTypeError(f"metric {metric!r} is numeric; snapshot gave {type(value).__name__}")
    elif domain == "boolean":
        if not isinstance(value, bool):
            raise MetricTypeError(f"metric {metric!r} is boolean; snapshot gave {type(value).__name__}")
    elif domain == "enum":
        if not isinstance(value, str):
            raise MetricTypeError(f"metric {metric!r} is enum; snapshot gave {type(value).__name__}")
    else:  # custom, typed by the leaf itself
        expect = {"number": (int, float), "boolean": (bool,), "string": (str,)}[declared or "number"]
        if declared == "number" and isinstance(value, bool):
            raise MetricTypeError(f"metric {metric!r} declared number; snapshot gave bool")
        if not isinstance(value, expect):
            raise MetricTypeError(
                f"metric {metric!r} declared {declared}; snapshot gave {type(value).__name__}"
            )


def evaluate(node: Mapping[str, Any], metrics: Mapping[str, Any]) -> bool:
    """Execute a stopping expression against a metric snapshot. Strict by design."""
    kind = _node_kind(node)
    if kind == "leaf":
        metric = node["metric"]
        if metric not in metrics:
            raise MissingMetricError(
                f"metric {metric!r} is referenced by the stopping rule but absent from the "
                f"snapshot; a missing metric is NOT false"
            )
        domain = "custom" if metric.startswith(CUSTOM_PREFIX) else domain_of(metric)
        actual = metrics[metric]
        _check_snapshot_type(metric, domain, actual, node.get("value_type"))
        return bool(_COMPARATORS[node["op"]](actual, node["value"]))
    if kind == "all_of":
        return all(evaluate(child, metrics) for child in node["all_of"])
    if kind == "any_of":
        return any(evaluate(child, metrics) for child in node["any_of"])
    if kind == "not":
        return not evaluate(node["not"], metrics)
    spec = node["weighted"]
    total = sum(c["weight"] for c in spec["clauses"] if evaluate(c["when"], metrics))
    return total >= spec["threshold"]


def iter_leaves(node: Mapping[str, Any]):
    kind = _node_kind(node)
    if kind == "leaf":
        yield node
    elif kind in ("all_of", "any_of"):
        for child in node[kind]:
            yield from iter_leaves(child)
    elif kind == "not":
        yield from iter_leaves(node["not"])
    else:
        for clause in node["weighted"]["clauses"]:
            yield from iter_leaves(clause["when"])


def referenced_metrics(node: Mapping[str, Any]) -> set:
    return {leaf["metric"] for leaf in iter_leaves(node)}
