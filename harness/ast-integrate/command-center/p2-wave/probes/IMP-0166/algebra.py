#!/usr/bin/env python3
"""Typed stopping-rule predicate tree: ANY / ALL / NOT / WEIGHTED plus CMP atoms.

Three-valued Kleene evaluation. UNKNOWN (NOT-CHECKED / unbound) is never coerced
to False (which would let a stop pass by ignorance) and never coerced to True
(which would make ALL behave as ANY under partial evidence).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Union

TRUE = "TRUE"
FALSE = "FALSE"
UNKNOWN = "UNKNOWN"
Tri = str

RELS = (">=", "<=", "==", "!=", ">", "<")
KEYWORDS = frozenset(
    {"AND", "OR", "NOT", "ANY", "ALL", "WEIGHTED", "TRUE", "FALSE"}
)


class ParseError(ValueError):
    """Expression is not in the typed algebra."""


Node = Union["Cmp", "All", "Any", "Not", "Weighted", "Atom"]


@dataclass(frozen=True)
class Cmp:
    metric: str
    rel: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "CMP",
            "metric": self.metric,
            "rel": self.rel,
            "value": self.value,
        }


@dataclass(frozen=True)
class Atom:
    metric: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "ATOM", "metric": self.metric}


@dataclass(frozen=True)
class All:
    args: tuple[Node, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "ALL", "args": [a.to_dict() for a in self.args]}


@dataclass(frozen=True)
class Any:
    args: tuple[Node, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "ANY", "args": [a.to_dict() for a in self.args]}


@dataclass(frozen=True)
class Not:
    arg: Node

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "NOT", "arg": self.arg.to_dict()}


@dataclass(frozen=True)
class WeightedTerm:
    weight: float
    pred: Node

    def to_dict(self) -> dict[str, Any]:
        return {"weight": self.weight, "pred": self.pred.to_dict()}


@dataclass(frozen=True)
class Weighted:
    threshold: float
    terms: tuple[WeightedTerm, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "WEIGHTED",
            "threshold": self.threshold,
            "terms": [t.to_dict() for t in self.terms],
        }


def tree_to_dict(node: Node) -> dict[str, Any]:
    return node.to_dict()


class _Tok:
    def __init__(self, kind: str, value: Any, pos: int):
        self.kind = kind
        self.value = value
        self.pos = pos


class _Lexer:
    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.n = len(text)

    def _skip(self) -> None:
        while self.i < self.n and self.text[self.i].isspace():
            self.i += 1

    def tokens(self) -> list[_Tok]:
        out: list[_Tok] = []
        while True:
            self._skip()
            if self.i >= self.n:
                out.append(_Tok("EOF", None, self.i))
                return out
            pos = self.i
            ch = self.text[self.i]
            if ch in "(),{}:":
                self.i += 1
                out.append(_Tok(ch, ch, pos))
                continue
            if self.text.startswith(">=", self.i):
                self.i += 2
                out.append(_Tok("REL", ">=", pos))
                continue
            if self.text.startswith("<=", self.i):
                self.i += 2
                out.append(_Tok("REL", "<=", pos))
                continue
            if self.text.startswith("==", self.i):
                self.i += 2
                out.append(_Tok("REL", "==", pos))
                continue
            if self.text.startswith("!=", self.i):
                self.i += 2
                out.append(_Tok("REL", "!=", pos))
                continue
            if ch in "><":
                self.i += 1
                out.append(_Tok("REL", ch, pos))
                continue
            if ch in "\"'":
                out.append(self._string(ch, pos))
                continue
            if ch.isdigit() or (
                ch == "." and self.i + 1 < self.n and self.text[self.i + 1].isdigit()
            ):
                out.append(self._number(pos))
                continue
            if ch.isalpha() or ch == "_":
                j = self.i + 1
                while j < self.n and (self.text[j].isalnum() or self.text[j] == "_"):
                    j += 1
                word = self.text[self.i : j]
                self.i = j
                up = word.upper()
                if up in KEYWORDS:
                    if up in {"TRUE", "FALSE"}:
                        out.append(_Tok("BOOL", up == "TRUE", pos))
                    else:
                        out.append(_Tok(up, word, pos))
                else:
                    out.append(_Tok("IDENT", word, pos))
                continue
            raise ParseError(f"unexpected character {ch!r} at {pos}")

    def _string(self, quote: str, pos: int) -> _Tok:
        self.i += 1
        buf: list[str] = []
        while self.i < self.n:
            c = self.text[self.i]
            if c == quote:
                self.i += 1
                return _Tok("STR", "".join(buf), pos)
            if c == "\\":
                self.i += 1
                if self.i >= self.n:
                    raise ParseError(f"unterminated string at {pos}")
                buf.append(self.text[self.i])
                self.i += 1
                continue
            buf.append(c)
            self.i += 1
        raise ParseError(f"unterminated string at {pos}")

    def _number(self, pos: int) -> _Tok:
        j = self.i
        while j < self.n and self.text[j].isdigit():
            j += 1
        if j < self.n and self.text[j] == ".":
            j += 1
            while j < self.n and self.text[j].isdigit():
                j += 1
        raw = self.text[self.i : j]
        self.i = j
        if "." in raw:
            return _Tok("NUM", float(raw), pos)
        return _Tok("NUM", int(raw), pos)


class _Parser:
    def __init__(self, text: str):
        self.toks = _Lexer(text).tokens()
        self.k = 0

    def _peek(self) -> _Tok:
        return self.toks[self.k]

    def _eat(self, kind: str | None = None) -> _Tok:
        t = self._peek()
        if kind is not None and t.kind != kind:
            raise ParseError(f"expected {kind} at {t.pos}, got {t.kind}")
        self.k += 1
        return t

    def parse(self) -> Node:
        node = self._or()
        if self._peek().kind != "EOF":
            t = self._peek()
            raise ParseError(f"trailing tokens at {t.pos} ({t.kind})")
        return node

    def _or(self) -> Node:
        left = self._and()
        parts = [left]
        while self._peek().kind == "OR":
            self._eat("OR")
            parts.append(self._and())
        if len(parts) == 1:
            return parts[0]
        return Any(tuple(parts))

    def _and(self) -> Node:
        left = self._not()
        parts = [left]
        while self._peek().kind == "AND":
            self._eat("AND")
            parts.append(self._not())
        if len(parts) == 1:
            return parts[0]
        return All(tuple(parts))

    def _not(self) -> Node:
        if self._peek().kind == "NOT":
            self._eat("NOT")
            return Not(self._not())
        return self._primary()

    def _primary(self) -> Node:
        t = self._peek()
        if t.kind == "(":
            self._eat("(")
            node = self._or()
            self._eat(")")
            return node
        if t.kind == "ANY":
            return Any(self._paren_list())
        if t.kind == "ALL":
            return All(self._paren_list())
        if t.kind == "WEIGHTED":
            return self._weighted()
        if t.kind == "IDENT":
            ident = self._eat("IDENT").value
            if self._peek().kind == "REL":
                rel = self._eat("REL").value
                val = self._value()
                return Cmp(ident, rel, val)
            return Atom(ident)
        raise ParseError(f"expected expression at {t.pos}, got {t.kind}")

    def _paren_list(self) -> tuple[Node, ...]:
        self._eat()  # ANY/ALL
        self._eat("(")
        args = [self._or()]
        while self._peek().kind == ",":
            self._eat(",")
            args.append(self._or())
        self._eat(")")
        return tuple(args)

    def _weighted(self) -> Weighted:
        self._eat("WEIGHTED")
        self._eat("(")
        thr_tok = self._eat("NUM")
        threshold = float(thr_tok.value)
        self._eat(",")
        terms: list[WeightedTerm] = []
        while True:
            pred = self._or()
            self._eat(":")
            w = self._eat("NUM")
            terms.append(WeightedTerm(float(w.value), pred))
            if self._peek().kind == ",":
                self._eat(",")
                continue
            break
        self._eat(")")
        if not terms:
            raise ParseError("WEIGHTED requires at least one term")
        return Weighted(threshold, tuple(terms))

    def _value(self) -> Any:
        t = self._peek()
        if t.kind == "NUM":
            return self._eat("NUM").value
        if t.kind == "BOOL":
            return self._eat("BOOL").value
        if t.kind == "STR":
            return self._eat("STR").value
        if t.kind == "IDENT":
            return self._eat("IDENT").value
        raise ParseError(f"expected value at {t.pos}, got {t.kind}")


def parse(text: str) -> Node:
    if not isinstance(text, str) or not text.strip():
        raise ParseError("empty expression")
    return _Parser(text.strip()).parse()


def _tri_not(v: Tri) -> Tri:
    if v == TRUE:
        return FALSE
    if v == FALSE:
        return TRUE
    return UNKNOWN


def _tri_all(vals: Sequence[Tri]) -> Tri:
    if any(v == FALSE for v in vals):
        return FALSE
    if any(v == UNKNOWN for v in vals):
        return UNKNOWN
    return TRUE


def _tri_any(vals: Sequence[Tri]) -> Tri:
    if any(v == TRUE for v in vals):
        return TRUE
    if any(v == UNKNOWN for v in vals):
        return UNKNOWN
    return FALSE


def _is_unchecked(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.upper() in {"NOT-CHECKED", "UNKNOWN", ""}:
        return True
    return False


def _as_bool(value: Any) -> Tri | None:
    if isinstance(value, bool):
        return TRUE if value else FALSE
    if isinstance(value, str):
        up = value.upper()
        if up in {"TRUE", "YES", "PASS"}:
            return TRUE
        if up in {"FALSE", "NO"}:
            return FALSE
    if isinstance(value, (int, float)) and value in (0, 1) and not isinstance(value, bool):
        return None
    return None


def _norm_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        up = value.upper()
        if up == "TRUE":
            return True
        if up == "FALSE":
            return False
        return value
    if isinstance(value, (int, float)):
        return value
    return value


def _cmp(left: Any, rel: str, right: Any) -> Tri:
    if _is_unchecked(left):
        return UNKNOWN
    if rel in {"==", "!="}:
        lv, rv = _norm_scalar(left), _norm_scalar(right)
        if isinstance(lv, bool) and isinstance(rv, bool):
            eq = lv is rv
        elif isinstance(lv, (int, float)) and isinstance(rv, (int, float)) and not isinstance(
            lv, bool
        ) and not isinstance(rv, bool):
            eq = float(lv) == float(rv)
        elif isinstance(lv, str) and isinstance(rv, str):
            eq = lv == rv
        elif type(lv) is type(rv):
            eq = lv == rv
        else:
            eq = str(lv) == str(rv)
        if rel == "==":
            return TRUE if eq else FALSE
        return FALSE if eq else TRUE
    if isinstance(left, bool) or isinstance(right, bool):
        return UNKNOWN
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return UNKNOWN
    lf, rf = float(left), float(right)
    if rel == ">=":
        return TRUE if lf >= rf else FALSE
    if rel == "<=":
        return TRUE if lf <= rf else FALSE
    if rel == ">":
        return TRUE if lf > rf else FALSE
    if rel == "<":
        return TRUE if lf < rf else FALSE
    return UNKNOWN


def evaluate(node: Node, state: Mapping[str, Any]) -> Tri:
    """Evaluate a tree against a state mapping. Missing keys are UNKNOWN."""
    if isinstance(node, Cmp):
        if node.metric not in state:
            return UNKNOWN
        return _cmp(state[node.metric], node.rel, node.value)
    if isinstance(node, Atom):
        if node.metric not in state:
            return UNKNOWN
        val = state[node.metric]
        if _is_unchecked(val):
            return UNKNOWN
        tb = _as_bool(val)
        if tb is not None:
            return tb
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return TRUE if val != 0 else FALSE
        return UNKNOWN
    if isinstance(node, Not):
        return _tri_not(evaluate(node.arg, state))
    if isinstance(node, All):
        return _tri_all([evaluate(a, state) for a in node.args])
    if isinstance(node, Any):
        return _tri_any([evaluate(a, state) for a in node.args])
    if isinstance(node, Weighted):
        sure = 0.0
        possible = 0.0
        for term in node.terms:
            tri = evaluate(term.pred, state)
            if tri == TRUE:
                sure += term.weight
                possible += term.weight
            elif tri == UNKNOWN:
                possible += term.weight
        if sure + 1e-12 >= node.threshold:
            return TRUE
        if possible + 1e-12 < node.threshold:
            return FALSE
        return UNKNOWN
    raise TypeError(f"unknown node {type(node)!r}")


def evaluate_text(text: str, state: Mapping[str, Any]) -> Tri:
    return evaluate(parse(text), state)


def stop_decision(tri: Tri) -> str:
    """Map three-valued result to a run decision. UNKNOWN never stops."""
    if tri == TRUE:
        return "STOP"
    if tri == FALSE:
        return "CONTINUE"
    return "NOT-CHECKED"
