"""Composable Boolean stopping expressions for council runs (IMP-0308, TST-0281).

Grammar (lowest to highest precedence; keywords are case-insensitive)::

    expr        := or_expr
    or_expr     := and_expr ( OR and_expr )*
    and_expr    := not_expr ( AND not_expr )*
    not_expr    := NOT not_expr | primary
    primary     := '(' expr ')'
                 | ANY '(' expr ( ',' expr )* ')'          n-ary OR
                 | ALL '(' expr ( ',' expr )* ')'          n-ary AND
                 | comparison
                 | 'true' | 'false'
                 | metric                                  a Boolean-valued metric
    comparison  := ( metric | weighted ) REL rhs
    weighted    := WEIGHTED '(' term ( '+' term )* ')'     weighted sum of metrics
    term        := number '*' metric | metric '*' number | metric
    rhs         := number | 'true' | 'false' | quoted string | SYMBOL
    REL         := '>=' | '<=' | '==' | '!=' | '>' | '<'

A bare identifier on the LEFT of a relation is a metric; a bare identifier on the RIGHT
is a symbolic constant, so ``quality_gate == PASS`` compares the metric with ``"PASS"``.
``NOT`` binds a whole comparison (``NOT a >= 1`` is ``NOT (a >= 1)``) and tighter than
``AND``, which binds tighter than ``OR``.

Two evaluation APIs share one parser and one Kleene evaluator core:

* :func:`bind` / :func:`evaluate` (IMP-0308) are strict and two-valued: a metric that no
  producer or snapshot supplies raises :class:`BindError` at bind time. It never becomes
  a silent ``False`` that sits false forever.
* :func:`evaluate_source` / :func:`run_fixture` / :func:`validate_spec` (TST-0281) are
  three-valued: a metric bound as ``{"status": "NOT-CHECKED"}`` (or not bound at all)
  evaluates to :data:`NOT_CHECKED`; AND/OR/NOT propagate it with Kleene logic; it is
  never coerced to ``False`` (``NOT`` of an unchecked metric stays unchecked) and only a
  definite ``True`` stops. Malformed sources and side-effecting (impure) terms are
  rejected at spec-validation, before any round runs.

Everything here is deterministic: no clock, no pid, no randomness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence, Union

__all__ = [
    "AllOf",
    "And",
    "AnyOf",
    "BindError",
    "BoundExpression",
    "Comparison",
    "EvalResult",
    "EvaluationError",
    "LIVE_RUN_ROUNDS",
    "Literal",
    "Metric",
    "NOT_CHECKED",
    "Node",
    "Not",
    "Or",
    "ParseError",
    "SPEC_EXPRESSIONS",
    "SpecValidationError",
    "StoppingExprError",
    "Weighted",
    "WeightedTerm",
    "ast_to_dict",
    "bind",
    "census",
    "evaluate",
    "evaluate_source",
    "is_not_checked",
    "live_run",
    "parse",
    "referenced_metrics",
    "run_fixture",
    "spec_producers",
    "validate_spec",
]

# --------------------------------------------------------------------------- errors


class StoppingExprError(Exception):
    """Base class for every error raised by this module."""


class SpecValidationError(StoppingExprError):
    """The expression is rejected before any round is evaluated.

    ``phase`` names where the rejection happened (``"spec-validation"`` or ``"bind"``),
    ``reason`` is a short machine-readable code, ``source`` the offending text.
    """

    def __init__(
        self,
        message: str,
        *,
        phase: str = "spec-validation",
        reason: str = "invalid",
        source: str | None = None,
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.reason = reason
        self.source = source


class ParseError(SpecValidationError):
    """Malformed expression text; ``position`` is the character offset of the bad token."""

    def __init__(self, message: str, *, position: int, source: str) -> None:
        super().__init__(message, phase="spec-validation", reason="syntax", source=source)
        self.position = position


class BindError(SpecValidationError):
    """The expression names metrics that no producer or snapshot supplies.

    ``unproduced`` is the sorted list of those metric names.
    """

    def __init__(self, unproduced: Iterable[str], source: str, *, phase: str = "bind") -> None:
        names = sorted(set(unproduced))
        super().__init__(
            f"unproduced metrics {names!r} in {source!r}",
            phase=phase,
            reason="unproduced-metric",
            source=source,
        )
        self.unproduced = names


class EvaluationError(StoppingExprError):
    """A checked metric value has a type the expression cannot use.

    This is a data error, not ignorance: an unchecked metric is :data:`NOT_CHECKED`,
    never an :class:`EvaluationError`.
    """


# ------------------------------------------------------------ the Kleene unknown


class _NotChecked:
    """Kleene ``unknown``: the metric was not checked this round.

    It compares equal to any other ``_NotChecked`` (also one from a second import of this
    module under another package name) and to the string ``"NOT-CHECKED"``. It has NO
    truth value: ``bool(NOT_CHECKED)`` raises so that no code path can coerce ignorance
    into ``False`` (or ``True``) by accident.
    """

    __slots__ = ()
    TEXT = "NOT-CHECKED"
    _kleene_unknown = True

    def __repr__(self) -> str:
        return "NOT_CHECKED"

    def __str__(self) -> str:
        return self.TEXT

    def __eq__(self, other: object) -> bool:
        if other is self:
            return True
        if isinstance(other, str):
            return other == self.TEXT
        return getattr(other, "_kleene_unknown", False) is True

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self.TEXT)

    def __bool__(self) -> bool:
        raise TypeError(
            "NOT-CHECKED has no truth value; a stopping rule must not coerce an "
            "unchecked metric to False or True (test with is_not_checked())"
        )

    def __reduce__(self) -> tuple[Any, tuple[()]]:
        return (_not_checked, ())


def _not_checked() -> "_NotChecked":
    return NOT_CHECKED


NOT_CHECKED = _NotChecked()

Value = Union[bool, _NotChecked]


def is_not_checked(value: object) -> bool:
    """True when ``value`` is the Kleene unknown (from any import of this module)."""
    return isinstance(value, _NotChecked) or getattr(value, "_kleene_unknown", False) is True


def _json_value(value: object) -> object:
    return _NotChecked.TEXT if is_not_checked(value) else value


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ----------------------------------------------------------------------- AST nodes


class Node:
    """Base class of every parsed stopping-expression node (frozen dataclasses)."""

    __slots__ = ()


@dataclass(frozen=True)
class Literal(Node):
    """The Boolean literal ``true`` / ``false``."""

    value: bool


@dataclass(frozen=True)
class Metric(Node):
    """A metric reference. In Boolean position its value must be a ``bool``."""

    name: str


@dataclass(frozen=True)
class WeightedTerm:
    """One ``weight * metric`` term of a ``WEIGHTED(...)`` sum."""

    weight: Union[int, float]
    metric: str


@dataclass(frozen=True)
class Weighted(Node):
    """``WEIGHTED(w1 * m1 + w2 * m2 ...)``: a weighted sum, only valid left of a REL."""

    terms: tuple[WeightedTerm, ...]


@dataclass(frozen=True)
class Comparison(Node):
    """``lhs REL value``. ``value_kind`` is number, bool, string or symbol."""

    lhs: Union[Metric, Weighted]
    rel: str
    value: Any
    value_kind: str


@dataclass(frozen=True)
class Not(Node):
    """Kleene negation."""

    arg: Node


@dataclass(frozen=True)
class And(Node):
    """Infix conjunction (``a AND b AND c`` is one node with three args)."""

    args: tuple[Node, ...]


@dataclass(frozen=True)
class Or(Node):
    """Infix disjunction."""

    args: tuple[Node, ...]


@dataclass(frozen=True)
class AnyOf(Node):
    """``ANY(e1, e2, ...)``: n-ary disjunction written as a call."""

    args: tuple[Node, ...]


@dataclass(frozen=True)
class AllOf(Node):
    """``ALL(e1, e2, ...)``: n-ary conjunction written as a call."""

    args: tuple[Node, ...]


# ------------------------------------------------------------------------- tokens

_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<number>-?\d+(?:\.\d+)?)
  | (?P<string>"[^"]*"|'[^']*')
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<rel>>=|<=|==|!=|>|<)
  | (?P<punct>[(),*+])
    """,
    re.VERBOSE,
)

_KEYWORDS = frozenset({"AND", "OR", "NOT", "ANY", "ALL", "WEIGHTED", "TRUE", "FALSE"})
_PUNCT_KINDS = {"(": "LPAREN", ")": "RPAREN", ",": "COMMA", "*": "STAR", "+": "PLUS"}
_RELATIONS = ("<", ">", "==", "!=", ">=", "<=")


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str | None
    pos: int


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    length = len(source)
    while index < length:
        match = _TOKEN_RE.match(source, index)
        if match is None:
            raise ParseError(
                f"unexpected character {source[index]!r} at {index}",
                position=index,
                source=source,
            )
        kind = match.lastgroup or ""
        text = match.group(0)
        if kind == "number":
            tokens.append(_Token("NUMBER", text, index))
        elif kind == "string":
            tokens.append(_Token("STRING", text, index))
        elif kind == "ident":
            upper = text.upper()
            tokens.append(_Token(upper if upper in _KEYWORDS else "IDENT", text, index))
        elif kind == "rel":
            tokens.append(_Token("REL", text, index))
        elif kind == "punct":
            tokens.append(_Token(_PUNCT_KINDS[text], text, index))
        index = match.end()
    tokens.append(_Token("EOF", None, length))
    return tokens


def _number(text: str) -> Union[int, float]:
    return float(text) if "." in text else int(text)


# ------------------------------------------------------------------------- parser


class _Parser:
    """Recursive-descent parser over the token list; one instance per source string."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens = _tokenize(source)
        self.index = 0

    # -- helpers
    def _peek(self) -> _Token:
        return self.tokens[self.index]

    def _advance(self) -> _Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _error(self, expected: str, token: _Token) -> ParseError:
        return ParseError(
            f"expected {expected}, got {token.kind} ({token.text!r}) at {token.pos}",
            position=token.pos,
            source=self.source,
        )

    def _expect(self, kind: str, expected: str) -> _Token:
        token = self._peek()
        if token.kind != kind:
            raise self._error(expected, token)
        return self._advance()

    # -- grammar
    def parse(self) -> Node:
        if self._peek().kind == "EOF":
            raise self._error("an expression", self._peek())
        node = self._or_expr()
        trailing = self._peek()
        if trailing.kind != "EOF":
            raise self._error("end of expression", trailing)
        return node

    def _or_expr(self) -> Node:
        args = [self._and_expr()]
        while self._peek().kind == "OR":
            self._advance()
            args.append(self._and_expr())
        return args[0] if len(args) == 1 else Or(tuple(args))

    def _and_expr(self) -> Node:
        args = [self._not_expr()]
        while self._peek().kind == "AND":
            self._advance()
            args.append(self._not_expr())
        return args[0] if len(args) == 1 else And(tuple(args))

    def _not_expr(self) -> Node:
        if self._peek().kind == "NOT":
            self._advance()
            return Not(self._not_expr())
        return self._primary()

    def _primary(self) -> Node:
        token = self._peek()
        if token.kind == "LPAREN":
            self._advance()
            node = self._or_expr()
            self._expect("RPAREN", ")")
            return node
        if token.kind in ("ANY", "ALL"):
            self._advance()
            self._expect("LPAREN", "(")
            args = [self._or_expr()]
            while self._peek().kind == "COMMA":
                self._advance()
                args.append(self._or_expr())
            self._expect("RPAREN", ")")
            return AnyOf(tuple(args)) if token.kind == "ANY" else AllOf(tuple(args))
        if token.kind == "WEIGHTED":
            return self._comparison_tail(self._weighted())
        if token.kind in ("TRUE", "FALSE"):
            self._advance()
            return Literal(token.kind == "TRUE")
        if token.kind == "IDENT":
            self._advance()
            metric = Metric(str(token.text))
            if self._peek().kind == "REL":
                return self._comparison_tail(metric)
            return metric
        raise self._error("atom", token)

    def _comparison_tail(self, lhs: Union[Metric, Weighted]) -> Comparison:
        rel = str(self._expect("REL", "a relational operator").text)
        token = self._peek()
        if token.kind == "NUMBER":
            self._advance()
            return Comparison(lhs, rel, _number(str(token.text)), "number")
        if token.kind in ("TRUE", "FALSE"):
            self._advance()
            return Comparison(lhs, rel, token.kind == "TRUE", "bool")
        if token.kind == "STRING":
            self._advance()
            return Comparison(lhs, rel, str(token.text)[1:-1], "string")
        if token.kind == "IDENT":
            self._advance()
            return Comparison(lhs, rel, str(token.text), "symbol")
        raise self._error("a comparison operand", token)

    def _weighted(self) -> Weighted:
        self._expect("WEIGHTED", "WEIGHTED")
        self._expect("LPAREN", "(")
        terms = [self._term()]
        while self._peek().kind == "PLUS":
            self._advance()
            terms.append(self._term())
        self._expect("RPAREN", ")")
        return Weighted(tuple(terms))

    def _term(self) -> WeightedTerm:
        token = self._peek()
        if token.kind == "NUMBER":
            self._advance()
            self._expect("STAR", "*")
            name = self._expect("IDENT", "a metric name")
            return WeightedTerm(_number(str(token.text)), str(name.text))
        if token.kind == "IDENT":
            self._advance()
            if self._peek().kind == "STAR":
                self._advance()
                weight = self._expect("NUMBER", "a weight")
                return WeightedTerm(_number(str(weight.text)), str(token.text))
            return WeightedTerm(1, str(token.text))
        raise self._error("a weighted term", token)


def parse(source: str) -> Node:
    """Parse ``source`` into an AST; malformed text raises :class:`ParseError`.

    :class:`ParseError` is a :class:`SpecValidationError` with ``phase="spec-validation"``.
    """
    if not isinstance(source, str):
        raise TypeError(f"stopping expression must be a str, got {type(source).__name__}")
    return _Parser(source).parse()


def referenced_metrics(node: Union[Node, str]) -> frozenset[str]:
    """Every metric name the expression reads (symbols right of a REL are not metrics)."""
    if isinstance(node, str):
        node = parse(node)
    names: set[str] = set()
    _collect_metrics(node, names)
    return frozenset(names)


def _collect_metrics(node: Node, names: set[str]) -> None:
    if isinstance(node, Metric):
        names.add(node.name)
    elif isinstance(node, Weighted):
        names.update(term.metric for term in node.terms)
    elif isinstance(node, Comparison):
        _collect_metrics(node.lhs, names)
    elif isinstance(node, Not):
        _collect_metrics(node.arg, names)
    elif isinstance(node, (And, Or, AnyOf, AllOf)):
        for arg in node.args:
            _collect_metrics(arg, names)
    elif not isinstance(node, Literal):
        raise TypeError(f"not a stopping-expression node: {node!r}")


def ast_to_dict(node: Node) -> dict[str, Any]:
    """JSON-ready tree: ``cmp``/``and``/``or``/``not``/``any``/``all``/``weighted``/``lit``/``var``."""
    if isinstance(node, Literal):
        return {"op": "lit", "value": node.value}
    if isinstance(node, Metric):
        return {"op": "var", "var": node.name}
    if isinstance(node, Weighted):
        return {
            "op": "weighted",
            "terms": [{"weight": term.weight, "var": term.metric} for term in node.terms],
        }
    if isinstance(node, Comparison):
        out: dict[str, Any] = {"op": "cmp", "rel": node.rel, "value": node.value}
        if isinstance(node.lhs, Metric):
            out["var"] = node.lhs.name
        else:
            out["weighted"] = ast_to_dict(node.lhs)
        return out
    if isinstance(node, Not):
        return {"op": "not", "arg": ast_to_dict(node.arg)}
    if isinstance(node, (And, Or, AnyOf, AllOf)):
        op = {And: "and", Or: "or", AnyOf: "any", AllOf: "all"}[type(node)]
        return {"op": op, "args": [ast_to_dict(arg) for arg in node.args]}
    raise TypeError(f"not a stopping-expression node: {node!r}")


# ---------------------------------------------------------------- evaluator core

Resolver = Callable[[str], Any]


class _Evaluator:
    """Kleene three-valued evaluation of one AST against a metric resolver.

    ``resolve(name)`` returns the metric's checked value, or ``None`` / NOT_CHECKED when
    it was not checked. With ``short_circuit`` a conjunction stops at its first definite
    ``False`` and a disjunction at its first definite ``True``; an unknown operand never
    short-circuits because a later operand can still decide the result.
    """

    def __init__(self, resolve: Resolver, *, short_circuit: bool) -> None:
        self._resolve = resolve
        self.short_circuit = short_circuit
        self.observed: list[str] = []
        self.unchecked: list[str] = []
        self.short_circuited = False

    def metric(self, name: str) -> Any:
        value = self._resolve(name)
        if name not in self.observed:
            self.observed.append(name)
        if value is None or is_not_checked(value):
            if name not in self.unchecked:
                self.unchecked.append(name)
            return NOT_CHECKED
        return value

    def eval(self, node: Node) -> Value:
        if isinstance(node, Literal):
            return node.value
        if isinstance(node, Metric):
            value = self.metric(node.name)
            if is_not_checked(value) or isinstance(value, bool):
                return value
            raise EvaluationError(
                f"metric {node.name!r} is used as a Boolean but produced "
                f"{type(value).__name__} {value!r}"
            )
        if isinstance(node, Comparison):
            return self._compare(node)
        if isinstance(node, Not):
            value = self.eval(node.arg)
            return value if is_not_checked(value) else (not value)
        if isinstance(node, (And, AllOf)):
            return self._conjunction(node.args)
        if isinstance(node, (Or, AnyOf)):
            return self._disjunction(node.args)
        raise TypeError(f"not a stopping-expression node: {node!r}")

    def _conjunction(self, args: Sequence[Node]) -> Value:
        unknown = False
        definite_false = False
        for position, arg in enumerate(args):
            value = self.eval(arg)
            if value is False:
                if self.short_circuit:
                    if position + 1 < len(args):
                        self.short_circuited = True
                    return False
                definite_false = True
            elif is_not_checked(value):
                unknown = True
        if definite_false:
            return False
        return NOT_CHECKED if unknown else True

    def _disjunction(self, args: Sequence[Node]) -> Value:
        unknown = False
        definite_true = False
        for position, arg in enumerate(args):
            value = self.eval(arg)
            if value is True:
                if self.short_circuit:
                    if position + 1 < len(args):
                        self.short_circuited = True
                    return True
                definite_true = True
            elif is_not_checked(value):
                unknown = True
        if definite_true:
            return True
        return NOT_CHECKED if unknown else False

    def _operand(self, lhs: Union[Metric, Weighted]) -> Any:
        if isinstance(lhs, Metric):
            return self.metric(lhs.name)
        total = 0.0
        unknown = False
        for term in lhs.terms:
            value = self.metric(term.metric)
            if is_not_checked(value):
                unknown = True
                continue
            if not _is_number(value):
                raise EvaluationError(
                    f"WEIGHTED term {term.metric!r} needs a number, got "
                    f"{type(value).__name__} {value!r}"
                )
            total += term.weight * value
        return NOT_CHECKED if unknown else total

    def _compare(self, node: Comparison) -> Value:
        left = self._operand(node.lhs)
        if is_not_checked(left):
            return NOT_CHECKED
        right = node.value
        if node.rel == "==":
            return bool(left == right)
        if node.rel == "!=":
            return bool(left != right)
        if not (_is_number(left) and _is_number(right)):
            raise EvaluationError(
                f"{node.rel!r} needs numeric operands, got {left!r} and {right!r}"
            )
        if node.rel == ">=":
            return bool(left >= right)
        if node.rel == "<=":
            return bool(left <= right)
        if node.rel == ">":
            return bool(left > right)
        return bool(left < right)


# ------------------------------------------- strict two-valued API (IMP-0308)

Producer = Callable[[int], Any]

SPEC_EXPRESSIONS: tuple[tuple[str, int, str], ...] = (
    ("E1", 10937, "unique_ideas >= 100 AND completeness_score >= 0.90"),
    ("E2", 10938, "consensus >= 0.95 AND no_new_objection_rounds >= 2"),
    ("E3", 10939, "unanimity == true OR max_rounds == 12"),
    ("E4", 10940, "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0"),
    ("E5", 10941, "evidence_saturation == true OR time_minutes >= 180"),
    ("E6", 10942, "proof_of_impossibility == true"),
)
"""The six catalog stopping examples as ``(id, spec line, source)``."""

LIVE_RUN_ROUNDS = 12


def _evaluate_snapshot(node: Node, source: str, snapshot: Mapping[str, Any]) -> Value:
    missing = sorted(name for name in referenced_metrics(node) if name not in snapshot)
    if missing:
        raise BindError(missing, source)
    # Snapshot reads are pure, so full evaluation costs nothing and surfaces a badly typed
    # metric on every round instead of only when the left arm happens to flip.
    evaluator = _Evaluator(lambda name: snapshot[name], short_circuit=False)
    return evaluator.eval(node)


@dataclass(frozen=True, eq=False)
class BoundExpression:
    """An expression whose every metric has a runtime producer ``f(round) -> value``."""

    source: str
    node: Node
    metrics: tuple[str, ...]
    producers: Mapping[str, Producer]

    def snapshot(self, round_index: int) -> dict[str, Any]:
        """Ask every bound producer for its value on 1-based ``round_index``."""
        if isinstance(round_index, bool) or not isinstance(round_index, int) or round_index < 1:
            raise ValueError(f"round_index must be a positive int (1-based), got {round_index!r}")
        return {name: self.producers[name](round_index) for name in self.metrics}

    def evaluate(self, snapshot: Mapping[str, Any]) -> Value:
        """Evaluate against a metric snapshot; a missing metric is a :class:`BindError`."""
        return _evaluate_snapshot(self.node, self.source, snapshot)

    def evaluate_round(self, round_index: int) -> tuple[Value, dict[str, Any]]:
        """Produce the round's snapshot and evaluate it: ``(value, snapshot)``."""
        snapshot = self.snapshot(round_index)
        return self.evaluate(snapshot), snapshot

    def ast(self) -> dict[str, Any]:
        """The JSON-ready tree of the bound expression."""
        return ast_to_dict(self.node)


def bind(source: str, producers: Mapping[str, Producer]) -> BoundExpression:
    """Parse ``source`` and bind every metric to ``producers[name]``.

    Raises :class:`BindError` (listing the ``unproduced`` names) when a referenced metric
    has no producer, so a typo or an unimplemented metric fails now, not at round 12.
    """
    node = parse(source)
    metrics = tuple(sorted(referenced_metrics(node)))
    missing = [name for name in metrics if name not in producers]
    if missing:
        raise BindError(missing, source)
    for name in metrics:
        if not callable(producers[name]):
            raise TypeError(f"producer for metric {name!r} is not callable: {producers[name]!r}")
    return BoundExpression(source, node, metrics, {name: producers[name] for name in metrics})


def evaluate(source: str, snapshot: Mapping[str, Any]) -> Value:
    """Strict one-shot evaluation of ``source`` against a metric snapshot.

    Every referenced metric must be present in ``snapshot`` or :class:`BindError` is
    raised; the result is a ``bool`` when every value is checked (a ``None`` value is
    NOT-CHECKED and propagates as :data:`NOT_CHECKED`).
    """
    return _evaluate_snapshot(parse(source), source, snapshot)


def census(sources: Iterable[str], producers: Mapping[str, Producer]) -> list[dict[str, Any]]:
    """One row per (expression, metric): is the metric produced at runtime?"""
    rows: list[dict[str, Any]] = []
    for source in sources:
        for metric in sorted(referenced_metrics(parse(source))):
            produced = metric in producers
            rows.append(
                {
                    "metric": metric,
                    "produced": produced,
                    "producer": metric if produced else None,
                    "referenced_by": source,
                }
            )
    return rows


# The 12-round fixture behind live_run(): a council that gathers ideas, converges, passes
# its quality gate, saturates its evidence and finally proves impossibility, so every one
# of the six spec expressions is false early and true by round 12.


def _unique_ideas(round_index: int) -> int:
    return 10 * round_index


def _completeness_score(round_index: int) -> float:
    return min(0.95, round(0.10 + 0.08 * round_index, 2))


def _consensus(round_index: int) -> float:
    return min(0.99, round(0.40 + 0.06 * round_index, 2))


def _no_new_objection_rounds(round_index: int) -> int:
    return max(0, round_index - 8)


def _unanimity(round_index: int) -> bool:
    return round_index >= 11


def _max_rounds(round_index: int) -> int:
    return round_index


def _quality_gate(round_index: int) -> str:
    return "PASS" if round_index >= 9 else "HOLD"


def _unresolved_load_bearing_counterexample(round_index: int) -> int:
    return max(0, 4 - round_index // 3)


def _evidence_saturation(round_index: int) -> bool:
    return round_index >= 10


def _time_minutes(round_index: int) -> int:
    return 15 * round_index


def _proof_of_impossibility(round_index: int) -> bool:
    return round_index >= 12


def spec_producers() -> dict[str, Producer]:
    """Runtime producers ``f(round) -> value`` for every metric the six spec lines name."""
    return {
        "unique_ideas": _unique_ideas,
        "completeness_score": _completeness_score,
        "consensus": _consensus,
        "no_new_objection_rounds": _no_new_objection_rounds,
        "unanimity": _unanimity,
        "max_rounds": _max_rounds,
        "quality_gate": _quality_gate,
        "unresolved_load_bearing_counterexample": _unresolved_load_bearing_counterexample,
        "evidence_saturation": _evidence_saturation,
        "time_minutes": _time_minutes,
        "proof_of_impossibility": _proof_of_impossibility,
    }


def live_run(
    rounds: int = LIVE_RUN_ROUNDS,
    expressions: Sequence[tuple[str, int, str]] = SPEC_EXPRESSIONS,
    producers: Mapping[str, Producer] | None = None,
) -> dict[str, Any]:
    """Bind every expression and evaluate it on each round, recording every bound metric.

    Returns ``per_round`` (round, per-expression value and ``bound_metrics``), ``series``
    (value per round per expression), ``changed_during_run`` (did the value flip) and
    ``final`` (value on the last round).
    """
    if rounds < 1:
        raise ValueError(f"rounds must be >= 1, got {rounds!r}")
    active = spec_producers() if producers is None else producers
    bound = [(eid, line, bind(source, active)) for eid, line, source in expressions]
    series: dict[str, list[Value]] = {eid: [] for eid, _, _ in bound}
    per_round: list[dict[str, Any]] = []
    for round_index in range(1, rounds + 1):
        row: dict[str, Any] = {"round": round_index, "expressions": []}
        for eid, line, expression in bound:
            value, snapshot = expression.evaluate_round(round_index)
            series[eid].append(value)
            row["expressions"].append(
                {
                    "id": eid,
                    "spec_line": line,
                    "source": expression.source,
                    "value": value,
                    "bound_metrics": {name: snapshot[name] for name in sorted(snapshot)},
                }
            )
        per_round.append(row)
    return {
        "rounds": rounds,
        "expressions": [
            {"id": eid, "spec_line": line, "source": b.source, "metrics": list(b.metrics)}
            for eid, line, b in bound
        ],
        "per_round": per_round,
        "series": series,
        "changed_during_run": {eid: len(set(values)) > 1 for eid, values in series.items()},
        "final": {eid: values[-1] for eid, values in series.items()},
    }


# ------------------------------------- three-valued runtime API (TST-0281)


@dataclass(frozen=True)
class EvalResult:
    """Outcome of :func:`evaluate_source`.

    ``value`` is ``True``, ``False`` or :data:`NOT_CHECKED`; ``stop`` is true only for a
    definite ``True``. ``observed`` lists the metrics actually read (evaluation order),
    ``unchecked`` those that were NOT-CHECKED or unbound, ``short_circuited`` whether an
    operand was skipped, ``mode`` is ``short-circuit`` or ``full``, ``ast`` is the
    :func:`ast_to_dict` form of the evaluated expression.
    """

    source: str
    value: Value
    stop: bool
    observed: list[str]
    unchecked: list[str]
    short_circuited: bool
    mode: str
    ast: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready copy (NOT_CHECKED becomes the string ``"NOT-CHECKED"``)."""
        return {
            "source": self.source,
            "ast": dict(self.ast),
            "value": _json_value(self.value),
            "stop": self.stop,
            "observed": list(self.observed),
            "unchecked": list(self.unchecked),
            "short_circuited": self.short_circuited,
            "mode": self.mode,
        }


def _binding_resolver(bindings: Mapping[str, Any] | None) -> Resolver:
    """Read metrics from a bindings mapping.

    A binding is either ``{"status": "CHECKED", "value": v}``, ``{"status":
    "NOT-CHECKED"}`` (each may carry ``"observe": callable`` that is called with the
    metric name when the term is read, and ``"impure": True``), or a raw checked value.
    An unbound metric is NOT-CHECKED.
    """
    table: dict[str, Any] = dict(bindings or {})

    def resolve(name: str) -> Any:
        if name not in table:
            return NOT_CHECKED
        entry = table[name]
        if isinstance(entry, Mapping) and "status" in entry:
            observe = entry.get("observe")
            if callable(observe):
                observe(name)
            status = str(entry["status"]).upper().replace("_", "-")
            if status == _NotChecked.TEXT:
                return NOT_CHECKED
            if status != "CHECKED":
                raise EvaluationError(f"metric {name!r} has unknown status {entry['status']!r}")
            return entry.get("value")
        return entry

    return resolve


def _impure_metrics(node: Node, bindings: Mapping[str, Any] | None) -> list[str]:
    if not bindings:
        return []
    impure: list[str] = []
    for name in sorted(referenced_metrics(node)):
        entry = bindings.get(name)
        if isinstance(entry, Mapping) and entry.get("impure"):
            impure.append(name)
    return impure


def validate_spec(
    source: str,
    producers: Iterable[str] | Mapping[str, Any] | None = None,
    bindings: Mapping[str, Any] | None = None,
) -> Node:
    """Reject a bad spec before round 1; return its AST when it is acceptable.

    * malformed text -> :class:`ParseError` (``phase="spec-validation"``)
    * ``producers`` given and a referenced metric has none -> :class:`BindError`
      (``phase="spec-validation"``, ``unproduced`` lists them)
    * ``bindings`` given and a referenced metric is ``impure`` -> :class:`SpecValidationError`
      (``reason="impure-term"``): short-circuit evaluation would skip its side effect, so
      such a term may only run under ``force_full=True``.
    """
    node = parse(source)
    metrics = referenced_metrics(node)
    if producers is not None:
        available = set(producers)
        missing = sorted(name for name in metrics if name not in available)
        if missing:
            raise BindError(missing, source, phase="spec-validation")
    impure = _impure_metrics(node, bindings)
    if impure:
        raise SpecValidationError(
            f"impure (side-effecting) terms {impure!r} in {source!r}: short-circuit "
            "evaluation would skip their effects; evaluate with force_full=True",
            reason="impure-term",
            source=source,
        )
    return node


def _evaluate_node(
    node: Node,
    source: str,
    bindings: Mapping[str, Any] | None,
    *,
    force_full: bool,
) -> EvalResult:
    if not force_full:
        impure = _impure_metrics(node, bindings)
        if impure:
            raise SpecValidationError(
                f"impure (side-effecting) terms {impure!r} in {source!r} need force_full=True",
                reason="impure-term",
                source=source,
            )
    evaluator = _Evaluator(_binding_resolver(bindings), short_circuit=not force_full)
    value = evaluator.eval(node)
    return EvalResult(
        source=source,
        value=value,
        stop=value is True,
        observed=list(evaluator.observed),
        unchecked=sorted(evaluator.unchecked),
        short_circuited=evaluator.short_circuited,
        mode="full" if force_full else "short-circuit",
        ast=ast_to_dict(node),
    )


def evaluate_source(
    source: str,
    bindings: Mapping[str, Any] | None = None,
    *,
    force_full: bool = False,
) -> EvalResult:
    """Three-valued evaluation of ``source`` against per-metric bindings.

    Kleene semantics: ``AND`` is false if any operand is false, else unknown if any is
    NOT-CHECKED; ``OR`` is true if any operand is true, else unknown if any is
    NOT-CHECKED; ``NOT`` of NOT-CHECKED is NOT-CHECKED. ``stop`` is true only for a
    definite ``True``, so ignorance never stops a council. Pure expressions short-circuit
    (a false left arm skips the right arm); ``force_full=True`` evaluates every term,
    which is required when any bound term is impure.
    """
    return _evaluate_node(parse(source), source, bindings, force_full=force_full)


def run_fixture(
    source: str,
    rounds: Sequence[Mapping[str, Any]],
    producers: Iterable[str] | Mapping[str, Any] | None = None,
    *,
    force_full: bool = False,
) -> dict[str, Any]:
    """Validate ``source`` once, then evaluate it round by round until the first stop.

    ``rounds`` is the per-round bindings, in order. Validation happens before round 1, so
    a malformed spec never reaches a round. ``stop_round`` is the 1-based index of the
    first round whose value is a definite ``True`` (``None`` when it never stops).
    """
    node = validate_spec(source, producers=producers)
    trace: list[dict[str, Any]] = []
    stop_round: int | None = None
    for index, bindings in enumerate(rounds, start=1):
        result = _evaluate_node(node, source, bindings, force_full=force_full)
        trace.append(
            {
                "round": index,
                "value": _json_value(result.value),
                "stop": result.stop,
                "unchecked": list(result.unchecked),
            }
        )
        if result.stop:
            stop_round = index
            break
    return {
        "source": source,
        "ast": ast_to_dict(node),
        "rounds_total": len(rounds),
        "rounds_evaluated": len(trace),
        "stop_round": stop_round,
        "stopped": stop_round is not None,
        "trace": trace,
    }
