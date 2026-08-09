"""The stopping / convergence expression grammar - parser and evaluator.

Why this exists
---------------
The spec mandates six *executable* stopping expressions
(``_USER-PROMPTS.md:10937-10942``) and composable ``ANY``/``ALL``/``NOT``/weighted logic
(10760, 10931). A schema can only assert that a string is present. If nothing ever parses
that string, the "composable stopping rules" capability is decorative: a typo'd rule would
sit in a certified workflow and silently never fire. This module makes the grammar real, so
``DSL-SEM-007`` can assert every expression in a workflow parses, and so an evaluator exists
for the runner.

Grammar (precedence low -> high)::

    or_expr   := and_expr (('OR' | '||') and_expr)*
    and_expr  := not_expr (('AND' | '&&') not_expr)*
    not_expr  := ('NOT' | '!') not_expr | primary
    primary   := '(' or_expr ')' | comparison | value
    comparison:= value ('==' | '!=' | '>=' | '<=' | '>' | '<') value
    value     := number | quoted-string | identifier

Relationship to ``platform/lib/councilspec/expression.py`` (a sibling contract unit)
-----------------------------------------------------------------------------------
That module is the CLOSED-vocabulary council parser: its leaves must be ``IDENT OP VALUE``
where ``IDENT`` is a metric registered in ``councilspec/registry.py``, and it returns a
canonical JSON tree. This module is the OPEN-vocabulary workflow evaluator: a leaf may be a
bare boolean identifier, an identifier-to-identifier comparison, or a dotted/hyphenated
metric that no council registry knows about (stage statuses, convergence metrics, routing
conditions). Neither subsumes the other, so this is a deliberate boundary, not a fork:

* council stopping-rule TEXT should be validated by ``councilspec.expression.parse`` -
  ``wfdsl.semantics`` delegates to it when the module is importable (DSL-SEM-014);
* the two implementations are cross-checked against each other on the six spec-mandated
  stopping expressions by ``test_expr.py::test_agrees_with_councilspec_on_spec_examples``,
  which is a genuine second signal: two independent parsers, one verdict each.

``AND``/``OR``/``NOT`` are case-insensitive. ``true``/``false`` (any case) are booleans. An
**ALL-CAPS** token (``PASS``, ``CONFIRMED``) is an enum CONSTANT and is never looked up, so
``quality_gate == PASS`` works without declaring ``PASS``. Every other identifier is a
METRIC: it is looked up in the evaluation context, and a metric that is absent raises
:class:`UnknownIdentifier` under the default ``strict=True`` - on either side of the
comparison. Silently evaluating an unmeasured metric to ``False`` is exactly the detector
failure this module exists to prevent; ``strict=False`` is the explicit, documented opt-out
for partial evaluation (a dry-run planner), and it returns ``False`` rather than raising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

__all__ = [
    "ExpressionError",
    "ParseError",
    "UnknownIdentifier",
    "Node",
    "parse",
    "evaluate",
    "identifiers",
    "evaluate_structured",
]


class ExpressionError(Exception):
    """Base class for expression problems."""


class ParseError(ExpressionError):
    """The expression string does not match the grammar."""


class UnknownIdentifier(ExpressionError):
    """An identifier in a value position is absent from the evaluation context."""


_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<op>==|!=|>=|<=|&&|\|\||[<>()!])
  | (?P<num>-?\d+(?:\.\d+)?)
  | (?P<str>'[^']*'|"[^"]*")
  | (?P<ident>[A-Za-z_][A-Za-z0-9_.\-]*)
    """,
    re.VERBOSE,
)

_KEYWORDS = {"and": "AND", "or": "OR", "not": "NOT"}
_CMP_OPS = {"==", "!=", ">=", "<=", ">", "<"}

#: An ALL-CAPS token is an enum CONSTANT (PASS, CONFIRMED, FAIL), never a metric. Same
#: convention as the sibling councilspec grammar, so the two agree on where a name ends and a
#: constant begins. A lower/mixed-case identifier is always a metric: it is looked up, and a
#: missing one RAISES under strict evaluation instead of quietly reading false.
_ENUM_CONSTANT_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _is_enum_constant(node: "Node") -> bool:
    return isinstance(node, Ident) and bool(_ENUM_CONSTANT_RE.match(node.name))


@dataclass(frozen=True)
class _Tok:
    kind: str  # 'op' | 'num' | 'str' | 'ident' | 'kw'
    text: str
    pos: int


def _tokenize(src: str) -> list[_Tok]:
    toks: list[_Tok] = []
    i = 0
    n = len(src)
    while i < n:
        m = _TOKEN_RE.match(src, i)
        if not m or m.end() == i:
            raise ParseError(f"unexpected character {src[i]!r} at offset {i} in {src!r}")
        i = m.end()
        if m.lastgroup == "ws":
            continue
        if m.lastgroup == "ident":
            low = m.group().lower()
            if low in _KEYWORDS:
                toks.append(_Tok("kw", _KEYWORDS[low], m.start()))
            else:
                toks.append(_Tok("ident", m.group(), m.start()))
            continue
        toks.append(_Tok(m.lastgroup or "op", m.group(), m.start()))
    return toks


# --------------------------------------------------------------------------- AST


class Node:
    """Base AST node."""

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> Any:  # pragma: no cover - abstract
        raise NotImplementedError

    def identifiers(self) -> set[str]:  # pragma: no cover - abstract
        raise NotImplementedError


@dataclass(frozen=True)
class Lit(Node):
    value: Any

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> Any:
        return self.value

    def identifiers(self) -> set[str]:
        return set()


@dataclass(frozen=True)
class Ident(Node):
    name: str

    def lookup(self, ctx: Mapping[str, Any]) -> Any:
        """Resolve a (possibly dotted) name, returning the ``_MISSING`` sentinel if absent."""
        cur: Any = ctx
        for part in self.name.split("."):
            if isinstance(cur, Mapping) and part in cur:
                cur = cur[part]
            else:
                return _MISSING
        return cur

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> Any:
        cur = self.lookup(ctx)
        if cur is _MISSING:
            if strict:
                raise UnknownIdentifier(f"identifier {self.name!r} is not in the evaluation context")
            return None
        return cur

    def identifiers(self) -> set[str]:
        return {self.name}


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "<missing>"


_MISSING = _Missing()


@dataclass(frozen=True)
class Cmp(Node):
    left: Node
    op: str
    right: Node

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> bool:
        missing = False
        if isinstance(self.left, Ident):
            lhs = self.left.lookup(ctx)
            if lhs is _MISSING:
                if strict:
                    raise UnknownIdentifier(f"identifier {self.left.name!r} is not in the evaluation context")
                missing, lhs = True, None
        else:
            lhs = self.left.evaluate(ctx, strict=strict)
        # An ALL-CAPS token on the RIGHT is an enum constant: `quality_gate == PASS` works
        # without declaring PASS. A lower/mixed-case name is a real metric and obeys `strict`.
        if _is_enum_constant(self.right):
            rhs: Any = self.right.name  # type: ignore[union-attr]
        elif isinstance(self.right, Ident):
            rhs = self.right.lookup(ctx)
            if rhs is _MISSING:
                if strict:
                    raise UnknownIdentifier(f"identifier {self.right.name!r} is not in the evaluation context")
                missing, rhs = True, None
        else:
            rhs = self.right.evaluate(ctx, strict=strict)
        if self.op == "==":
            return _eq(lhs, rhs)
        if self.op == "!=":
            return not _eq(lhs, rhs)
        if missing:
            # Explicit non-strict partial evaluation: an UNMEASURED operand cannot satisfy an
            # ordering comparison, so it reads False. Under the default strict=True this branch
            # is unreachable - the raise above fires instead, so an unmeasured metric can never
            # silently read False.
            return False
        if not isinstance(lhs, (int, float)) or not isinstance(rhs, (int, float)) or isinstance(lhs, bool) or isinstance(rhs, bool):
            raise ExpressionError(f"ordering comparison needs numbers, got {lhs!r} {self.op} {rhs!r}")
        if self.op == ">":
            return lhs > rhs
        if self.op == ">=":
            return lhs >= rhs
        if self.op == "<":
            return lhs < rhs
        if self.op == "<=":
            return lhs <= rhs
        raise ExpressionError(f"unsupported operator {self.op!r}")  # pragma: no cover

    def identifiers(self) -> set[str]:
        out = self.left.identifiers()
        if not _is_enum_constant(self.right):
            out |= self.right.identifiers()
        return out


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or (isinstance(a, bool) and isinstance(b, bool) and a == b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


@dataclass(frozen=True)
class And(Node):
    parts: tuple[Node, ...]

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> bool:
        return all(_truthy(p.evaluate(ctx, strict=strict)) for p in self.parts)

    def identifiers(self) -> set[str]:
        return set().union(*(p.identifiers() for p in self.parts))


@dataclass(frozen=True)
class Or(Node):
    parts: tuple[Node, ...]

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> bool:
        return any(_truthy(p.evaluate(ctx, strict=strict)) for p in self.parts)

    def identifiers(self) -> set[str]:
        return set().union(*(p.identifiers() for p in self.parts))


@dataclass(frozen=True)
class Not(Node):
    part: Node

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> bool:
        return not _truthy(self.part.evaluate(ctx, strict=strict))

    def identifiers(self) -> set[str]:
        return self.part.identifiers()


@dataclass(frozen=True)
class Weighted(Node):
    terms: tuple[tuple[Node, float], ...]
    threshold: float

    def evaluate(self, ctx: Mapping[str, Any], strict: bool = True) -> bool:
        total = 0.0
        for node, weight in self.terms:
            if _truthy(node.evaluate(ctx, strict=strict)):
                total += weight
        return total >= self.threshold

    def identifiers(self) -> set[str]:
        return set().union(*(n.identifiers() for n, _ in self.terms)) if self.terms else set()


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.upper() in {"TRUE", "PASS", "YES", "OK", "CONFIRMED"}
    if isinstance(v, (list, tuple, dict, set)):
        return len(v) > 0
    return bool(v)


# ------------------------------------------------------------------------- parser


class _Parser:
    def __init__(self, toks: Sequence[_Tok], src: str) -> None:
        self.toks = list(toks)
        self.i = 0
        self.src = src

    def peek(self) -> _Tok | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self) -> _Tok:
        if self.i >= len(self.toks):
            raise ParseError(f"unexpected end of expression in {self.src!r}")
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.parse_or()
        if self.i != len(self.toks):
            tok = self.toks[self.i]
            raise ParseError(f"trailing token {tok.text!r} at offset {tok.pos} in {self.src!r}")
        return node

    def parse_or(self) -> Node:
        parts = [self.parse_and()]
        while True:
            tok = self.peek()
            if tok and ((tok.kind == "kw" and tok.text == "OR") or (tok.kind == "op" and tok.text == "||")):
                self.take()
                parts.append(self.parse_and())
            else:
                break
        return parts[0] if len(parts) == 1 else Or(tuple(parts))

    def parse_and(self) -> Node:
        parts = [self.parse_not()]
        while True:
            tok = self.peek()
            if tok and ((tok.kind == "kw" and tok.text == "AND") or (tok.kind == "op" and tok.text == "&&")):
                self.take()
                parts.append(self.parse_not())
            else:
                break
        return parts[0] if len(parts) == 1 else And(tuple(parts))

    def parse_not(self) -> Node:
        tok = self.peek()
        if tok and ((tok.kind == "kw" and tok.text == "NOT") or (tok.kind == "op" and tok.text == "!")):
            self.take()
            return Not(self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        tok = self.peek()
        if tok is None:
            raise ParseError(f"unexpected end of expression in {self.src!r}")
        if tok.kind == "op" and tok.text == "(":
            self.take()
            node = self.parse_or()
            closing = self.take()
            if not (closing.kind == "op" and closing.text == ")"):
                raise ParseError(f"expected ')' at offset {closing.pos} in {self.src!r}")
            return node
        left = self.parse_value()
        nxt = self.peek()
        if nxt and nxt.kind == "op" and nxt.text in _CMP_OPS:
            self.take()
            right = self.parse_value()
            return Cmp(left, nxt.text, right)
        return left

    def parse_value(self) -> Node:
        tok = self.take()
        if tok.kind == "num":
            return Lit(float(tok.text) if "." in tok.text else int(tok.text))
        if tok.kind == "str":
            return Lit(tok.text[1:-1])
        if tok.kind == "ident":
            low = tok.text.lower()
            if low == "true":
                return Lit(True)
            if low == "false":
                return Lit(False)
            return Ident(tok.text)
        raise ParseError(f"expected a value at offset {tok.pos}, got {tok.text!r} in {self.src!r}")


def parse(expression: str) -> Node:
    """Parse the string form into an AST. Raises :class:`ParseError` on bad syntax."""
    if not isinstance(expression, str):
        raise ParseError(f"expression must be a string, got {type(expression).__name__}")
    if not expression.strip():
        raise ParseError("empty expression")
    return _Parser(_tokenize(expression), expression).parse()


def _from_structured(node: Any) -> Node:
    """Convert the structured (JSON tree) form into the same AST."""
    if isinstance(node, str):
        return parse(node)
    if not isinstance(node, Mapping):
        raise ParseError(f"structured expression must be an object or string, got {type(node).__name__}")
    keys = set(node)
    if keys == {"all"}:
        return And(tuple(_from_structured(x) for x in node["all"]))
    if keys == {"any"}:
        return Or(tuple(_from_structured(x) for x in node["any"]))
    if keys == {"not"}:
        return Not(_from_structured(node["not"]))
    if keys == {"cmp"}:
        c = node["cmp"]
        # In the structured form the RIGHT side is always a LITERAL: JSON already distinguishes
        # 100 from "PASS", so there is no need to guess whether a string is a metric reference.
        # An enum comparison therefore still works (`"PASS" == "PASS"`) without a lookup.
        return Cmp(Ident(str(c["left"])), str(c["op"]), Lit(c["right"]))
    if keys == {"weighted"}:
        w = node["weighted"]
        terms = tuple((_from_structured(t["expr"]), float(t["weight"])) for t in w["terms"])
        return Weighted(terms, float(w["threshold"]))
    raise ParseError(f"unrecognised structured expression keys: {sorted(keys)}")


def to_ast(expression: Any) -> Node:
    """Accept either form (string or structured) and return the AST."""
    return _from_structured(expression)


def evaluate(expression: Any, ctx: Mapping[str, Any], strict: bool = True) -> bool:
    """Evaluate either form against a context mapping."""
    return _truthy(to_ast(expression).evaluate(ctx, strict=strict))


def evaluate_structured(expression: Any, ctx: Mapping[str, Any], strict: bool = True) -> bool:
    """Backwards-compatible alias for :func:`evaluate`."""
    return evaluate(expression, ctx, strict=strict)


def identifiers(expression: Any) -> set[str]:
    """The identifier set an expression depends on (used by DSL-SEM-008)."""
    return to_ast(expression).identifiers()
