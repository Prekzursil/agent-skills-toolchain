#!/usr/bin/env python3
"""Composable stopping-expression parser and Kleene three-valued evaluator.

Atoms are metric comparisons. A missing metric is Unknown (NOT-CHECKED), never
silently coerced to False. STOP is emitted only when the expression is True.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

Tri = Optional[bool]  # True | False | None (Unknown)


def kleene_not(a: Tri) -> Tri:
    if a is None:
        return None
    return not a


def kleene_and(a: Tri, b: Tri) -> Tri:
    # False dominates; True∧True=True; otherwise Unknown.
    if a is False or b is False:
        return False
    if a is True and b is True:
        return True
    return None


def kleene_or(a: Tri, b: Tri) -> Tri:
    if a is True or b is True:
        return True
    if a is False and b is False:
        return False
    return None


@dataclass(frozen=True)
class Cmp:
    name: str
    op: str
    value: Any
    source: str


@dataclass(frozen=True)
class Unary:
    op: str
    inner: Any


@dataclass(frozen=True)
class Binary:
    op: str
    left: Any
    right: Any


class ParseError(ValueError):
    pass


_OPS = (">=", "<=", "==", "!=", ">", "<")


def _tokenize(text: str) -> list[tuple[str, Any]]:
    s = text.strip()
    i = 0
    n = len(s)
    out: list[tuple[str, Any]] = []
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in "()":
            out.append((c, c))
            i += 1
            continue
        if s.startswith(">=", i) or s.startswith("<=", i) or s.startswith("==", i) or s.startswith("!=", i):
            out.append(("OP", s[i : i + 2]))
            i += 2
            continue
        if c in "><":
            out.append(("OP", c))
            i += 1
            continue
        if c in "\"'":
            q = c
            j = i + 1
            buf = []
            while j < n and s[j] != q:
                buf.append(s[j])
                j += 1
            if j >= n:
                raise ParseError(f"unterminated string in {text!r}")
            out.append(("VAL", "".join(buf)))
            i = j + 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            raw = s[i:j]
            if "." in raw:
                out.append(("VAL", float(raw)))
            else:
                out.append(("VAL", int(raw)))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            upper = word.upper()
            if upper in {"AND", "OR", "NOT"}:
                out.append((upper, word))
            elif word == "true":
                out.append(("VAL", True))
            elif word == "false":
                out.append(("VAL", False))
            else:
                out.append(("ID", word))
            i = j
            continue
        raise ParseError(f"unexpected {c!r} in {text!r}")
    return out


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self) -> tuple[str, Any] | None:
        if self.i >= len(self.toks):
            return None
        return self.toks[self.i]

    def eat(self, kind: str | None = None) -> tuple[str, Any]:
        tok = self.peek()
        if tok is None:
            raise ParseError(f"unexpected end of {self.text!r}")
        if kind is not None and tok[0] != kind:
            raise ParseError(f"expected {kind} got {tok} in {self.text!r}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        node = self.parse_or()
        if self.peek() is not None:
            raise ParseError(f"trailing tokens {self.toks[self.i :]} in {self.text!r}")
        return node

    def parse_or(self) -> Any:
        node = self.parse_and()
        while self.peek() and self.peek()[0] == "OR":
            self.eat("OR")
            node = Binary("OR", node, self.parse_and())
        return node

    def parse_and(self) -> Any:
        node = self.parse_not()
        while self.peek() and self.peek()[0] == "AND":
            self.eat("AND")
            node = Binary("AND", node, self.parse_not())
        return node

    def parse_not(self) -> Any:
        if self.peek() and self.peek()[0] == "NOT":
            self.eat("NOT")
            return Unary("NOT", self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Any:
        tok = self.peek()
        if tok is None:
            raise ParseError(f"empty primary in {self.text!r}")
        if tok[0] == "(":
            self.eat("(")
            node = self.parse_or()
            self.eat(")")
            return node
        return self.parse_cmp()

    def parse_cmp(self) -> Cmp:
        name = self.eat("ID")[1]
        op = self.eat("OP")[1]
        kind, val = self.eat()
        if kind == "VAL":
            value = val
        elif kind == "ID":
            value = val
        else:
            raise ParseError(f"expected value, got {(kind, val)} in {self.text!r}")
        src = f"{name} {op} {self._fmt(value)}"
        return Cmp(name, op, value, src)

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)


def parse(text: str) -> Any:
    return _Parser(text).parse()


def collect_atoms(node: Any, acc: list[Cmp] | None = None) -> list[Cmp]:
    acc = acc if acc is not None else []
    if isinstance(node, Cmp):
        if all(a.source != node.source for a in acc):
            acc.append(node)
        return acc
    if isinstance(node, Unary):
        return collect_atoms(node.inner, acc)
    if isinstance(node, Binary):
        collect_atoms(node.left, acc)
        collect_atoms(node.right, acc)
        return acc
    raise TypeError(type(node))


def apply_cmp(left: Any, op: str, right: Any) -> bool:
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    raise ValueError(op)


def eval_cmp(node: Cmp, state: dict[str, Any]) -> Tri:
    if node.name not in state:
        return None
    return apply_cmp(state[node.name], node.op, node.value)


def eval_node(
    node: Any,
    state: dict[str, Any],
    and_fn: Callable[[Tri, Tri], Tri] = kleene_and,
    or_fn: Callable[[Tri, Tri], Tri] = kleene_or,
) -> Tri:
    if isinstance(node, Cmp):
        return eval_cmp(node, state)
    if isinstance(node, Unary) and node.op == "NOT":
        return kleene_not(eval_node(node.inner, state, and_fn, or_fn))
    if isinstance(node, Binary) and node.op == "AND":
        # Full evaluation (no short-circuit) so side-effecting terms cannot hide.
        left = eval_node(node.left, state, and_fn, or_fn)
        right = eval_node(node.right, state, and_fn, or_fn)
        return and_fn(left, right)
    if isinstance(node, Binary) and node.op == "OR":
        left = eval_node(node.left, state, and_fn, or_fn)
        right = eval_node(node.right, state, and_fn, or_fn)
        return or_fn(left, right)
    raise TypeError(type(node))


def force_value(atom: Cmp, want: Tri) -> Any:
    """A concrete metric value that makes `atom` True, False, or omit (Unknown)."""
    if want is None:
        return None
    op, val = atom.op, atom.value
    if op == ">=":
        if want:
            return val
        if isinstance(val, int) and not isinstance(val, bool):
            return val - 1
        return float(val) - 0.01
    if op == "<=":
        if want:
            return val
        if isinstance(val, int) and not isinstance(val, bool):
            return val + 1
        return float(val) + 0.01
    if op == ">":
        if isinstance(val, int) and not isinstance(val, bool):
            return val + 1 if want else val
        return float(val) + 0.01 if want else val
    if op == "<":
        if isinstance(val, int) and not isinstance(val, bool):
            return val - 1 if want else val
        return float(val) - 0.01 if want else val
    if op == "==":
        if want:
            return val
        if val is True:
            return False
        if val is False:
            return True
        if isinstance(val, str):
            return f"NOT-{val}" if val != "FAIL" else "PASS"
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val + 1
        return object()
    if op == "!=":
        if not want:
            return val
        if val is True:
            return False
        if val is False:
            return True
        if isinstance(val, str):
            return f"NOT-{val}"
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val + 1
        return object()
    raise ValueError(op)


def state_from_assignment(atoms: list[Cmp], wants: list[Tri]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for atom, want in zip(atoms, wants):
        if want is None:
            continue
        state[atom.name] = force_value(atom, want)
    return state


class StoppingRuntime:
    """Stops iff the expression evaluates to True. Unknown does not stop."""

    def __init__(
        self,
        expression: str,
        and_fn: Callable[[Tri, Tri], Tri] = kleene_and,
        or_fn: Callable[[Tri, Tri], Tri] = kleene_or,
    ) -> None:
        self.expression = expression
        self.ast = parse(expression)
        self.atoms = collect_atoms(self.ast)
        self.and_fn = and_fn
        self.or_fn = or_fn

    def evaluate(self, state: dict[str, Any]) -> Tri:
        return eval_node(self.ast, state, self.and_fn, self.or_fn)

    def decide(self, state: dict[str, Any]) -> str:
        v = self.evaluate(state)
        return "STOP" if v is True else "CONTINUE"
