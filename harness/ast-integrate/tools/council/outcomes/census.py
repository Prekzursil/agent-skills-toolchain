#!/usr/bin/env python3
"""Downstream-consumer census: which readers collapse council outcome kinds into PASS/FAIL?

Council outcomes come in the closed set of kinds defined in :mod:`council.outcomes.kinds`:
``NO-DECISION``, ``CONDITIONAL``, ``PROOF-OF-IMPOSSIBILITY`` and ``DECISION``. The first
three are *protected*: a consumer that remaps one of them onto a binary label (``PASS`` /
``FAIL`` and their aliases) destroys exactly the information the kind exists to carry. This
module walks Python source with :mod:`ast` -- nothing is imported or executed -- and reports,
per file, every place a protected kind is remapped onto a binary label.

Detected coercion shapes (the ``pattern`` value of each reported coercion):

``if-branch``           ``if kind == "NO-DECISION": return "FAIL"``
``if-branch-assign``    ``if kind == "NO-DECISION": verdict = "FAIL"``
``binary-else``         ``if kind == "DECISION": ... else: return "FAIL"`` -- every protected
                        kind the if/elif chain did not handle explicitly falls into the else
``binary-fallthrough``  a kind-guarded chain followed by a bare ``return "FAIL"``
``ifexp-binary``        ``"FAIL" if kind == "NO-DECISION" else ...``
``ifexp-else-binary``   ``"PASS" if kind == "DECISION" else "FAIL"``
``dict-map``            ``{"NO-DECISION": "FAIL", ...}``
``match-case``          ``match kind: case "NO-DECISION": return "FAIL"`` (and wildcard cases)

Classification per file:

``COERCES``         at least one coercion of a protected kind was found
``PRESERVES``       the file names an outcome kind or branches on one, and never coerces any
``NO-KIND-READER``  the file never touches outcome kinds (neither coercer nor preserver); a
                    read of some unrelated ``kind`` field alone does not make it a reader
``UNREADABLE``      the file could not be read or parsed

Kind *reads* are recognised structurally: a variable whose name contains ``kind``, an
``x["kind"]`` subscript, an ``x.kind`` attribute, ``x.get("kind")``, ``getattr(x, "kind")``.
Kind *constants* are string literals, module-level string bindings, and the ``KIND_*`` names
exported by :mod:`council.outcomes.kinds` (imported under any alias, or used via ``kinds.KIND_*``).
Collections in ``in`` tests resolve through module-level tuples/lists/sets and dict keys, so
``if kind in PROTECTED:`` with ``PROTECTED = ("NO-DECISION", ...)`` is understood.
"""
from __future__ import annotations

import ast
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from .kinds import (
    KIND_CONDITIONAL,
    KIND_DECISION,
    KIND_NO_DECISION,
    KIND_PROOF_OF_IMPOSSIBILITY,
    CollapseForbidden,
    OutcomeValidationError,
)

# Name -> kind string, for the constants council.outcomes.kinds exports.
KIND_NAMES: dict[str, str] = {
    "KIND_NO_DECISION": KIND_NO_DECISION,
    "KIND_CONDITIONAL": KIND_CONDITIONAL,
    "KIND_PROOF_OF_IMPOSSIBILITY": KIND_PROOF_OF_IMPOSSIBILITY,
    "KIND_DECISION": KIND_DECISION,
}
PROTECTED_KINDS: tuple[str, ...] = tuple(
    sorted((KIND_NO_DECISION, KIND_CONDITIONAL, KIND_PROOF_OF_IMPOSSIBILITY))
)
ALL_KINDS: frozenset[str] = frozenset(KIND_NAMES.values())
_PROTECTED: frozenset[str] = frozenset(PROTECTED_KINDS)
# Binary vocabularies a coercer collapses into. Matched case-insensitively after stripping.
BINARY_LABELS: frozenset[str] = frozenset(
    {"PASS", "FAIL", "PASSED", "FAILED", "SUCCESS", "FAILURE"}
)

CLASS_COERCES = "COERCES"
CLASS_PRESERVES = "PRESERVES"
CLASS_NO_READER = "NO-KIND-READER"
CLASS_UNREADABLE = "UNREADABLE"

_HANDLES_FIELD: dict[str, str] = {
    KIND_NO_DECISION: "handles_no_decision",
    KIND_CONDITIONAL: "handles_conditional",
    KIND_PROOF_OF_IMPOSSIBILITY: "handles_proof",
}


# --------------------------------------------------------------------------- resolution
class _ModuleScope:
    """Module-level constant bindings that kind guards may refer to by name."""

    def __init__(self, tree: ast.Module) -> None:
        self.strings: dict[str, str] = {}
        self.collections: dict[str, frozenset[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in KIND_NAMES:
                        self.strings[alias.asname or alias.name] = KIND_NAMES[alias.name]
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                text = self.string_of(value)
                if text is not None:
                    self.strings[target.id] = text
                    continue
                items = self.strings_in(value)
                if items is not None:
                    self.collections[target.id] = items

    def string_of(self, node: ast.AST | None) -> str | None:
        """Resolve ``node`` to a string constant, or ``None`` when it is not one."""
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.Name):
            if node.id in self.strings:
                return self.strings[node.id]
            return KIND_NAMES.get(node.id)
        if isinstance(node, ast.Attribute):
            return KIND_NAMES.get(node.attr)
        return None

    def strings_in(self, node: ast.AST | None) -> frozenset[str] | None:
        """Resolve a literal/bound collection to the set of string constants it holds."""
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            found = {self.string_of(elt) for elt in node.elts}
            found.discard(None)
            return frozenset(s for s in found if s is not None)
        if isinstance(node, ast.Dict):
            found = {self.string_of(key) for key in node.keys if key is not None}
            return frozenset(s for s in found if s is not None)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"set", "frozenset", "tuple", "list"} and len(node.args) == 1:
                return self.strings_in(node.args[0])
            return None
        if isinstance(node, ast.Name):
            return self.collections.get(node.id)
        return None

    def is_kind_expr(self, node: ast.AST | None) -> bool:
        """Is ``node`` a runtime read of an outcome kind (as opposed to a kind constant)?"""
        if isinstance(node, ast.Name):
            if node.id in self.strings or node.id in self.collections or node.id in KIND_NAMES:
                return False
            return "kind" in node.id.lower() and not node.id.isupper()
        if isinstance(node, ast.Attribute):
            attr = node.attr.lower()
            return attr == "kind" or attr.endswith("_kind")
        if isinstance(node, ast.Subscript):
            index = node.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, str):
                low = index.value.lower()
                return low == "kind" or low.endswith("_kind")
            return False
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get" and node.args:
                first = node.args[0]
                return (
                    isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                    and (first.value.lower() == "kind" or first.value.lower().endswith("_kind"))
                )
            if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
                second = node.args[1]
                return isinstance(second, ast.Constant) and second.value == "kind"
            if isinstance(func, ast.Name) and func.id == "str" and len(node.args) == 1:
                return self.is_kind_expr(node.args[0])
            return False
        if isinstance(node, ast.BoolOp):
            return any(self.is_kind_expr(value) for value in node.values)
        return False

    def binary_label(self, node: ast.AST | None) -> str | None:
        """Return the binary label ``node`` evaluates to (verbatim), or ``None``."""
        text = self.string_of(node)
        if text is None:
            return None
        return text if text.strip().upper() in BINARY_LABELS else None


@dataclass(frozen=True)
class _Guard:
    """A test whose truth depends on the outcome kind."""

    matched: frozenset[str]  # kinds (subset of ALL_KINDS) for which the test is true
    line: int


def _parse_guard(test: ast.AST, scope: _ModuleScope) -> _Guard | None:
    """Interpret ``test`` as a kind guard; ``None`` when it does not depend on a known kind."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        inner = _parse_guard(test.operand, scope)
        if inner is None:
            return None
        return _Guard(ALL_KINDS - inner.matched, inner.line)
    if isinstance(test, ast.BoolOp):
        guards = [g for g in (_parse_guard(v, scope) for v in test.values) if g is not None]
        if not guards:
            return None
        if isinstance(test.op, ast.And):
            matched = ALL_KINDS
            for guard in guards:
                matched &= guard.matched
        else:
            matched = frozenset()
            for guard in guards:
                matched |= guard.matched
        return _Guard(matched, guards[0].line)
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    op = test.ops[0]
    left, right = test.left, test.comparators[0]
    if isinstance(op, (ast.In, ast.NotIn)):
        if not scope.is_kind_expr(left):
            return None
        items = scope.strings_in(right)
        if items is None:
            return None
        kinds = items & ALL_KINDS
    elif isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
        if scope.is_kind_expr(left):
            const = scope.string_of(right)
        elif scope.is_kind_expr(right):
            const = scope.string_of(left)
        else:
            return None
        if const is None:
            return None
        kinds = frozenset({const}) & ALL_KINDS
    else:
        return None
    if not kinds:
        return None
    if isinstance(op, (ast.NotEq, ast.NotIn, ast.IsNot)):
        kinds = ALL_KINDS - kinds
    return _Guard(kinds, getattr(test, "lineno", 0))


def _branch_outcomes(stmts: list[ast.stmt], scope: _ModuleScope) -> list[tuple[str, str, int]]:
    """Binary labels a branch body produces directly: ``(label, "return"|"assign", line)``.

    Descends through plain control flow but stops at nested kind guards (they are analysed
    on their own) and nested function definitions.
    """
    found: list[tuple[str, str, int]] = []
    for stmt in stmts:
        if isinstance(stmt, ast.Return):
            label = scope.binary_label(stmt.value)
            if label is not None:
                found.append((label, "return", stmt.lineno))
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            label = scope.binary_label(stmt.value)
            if label is not None:
                found.append((label, "assign", stmt.lineno))
        elif isinstance(stmt, ast.If):
            if _parse_guard(stmt.test, scope) is None:
                found.extend(_branch_outcomes(stmt.body, scope))
                found.extend(_branch_outcomes(stmt.orelse, scope))
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            found.extend(_branch_outcomes(stmt.body, scope))
            found.extend(_branch_outcomes(stmt.orelse, scope))
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            found.extend(_branch_outcomes(stmt.body, scope))
        elif isinstance(stmt, ast.Try):
            found.extend(_branch_outcomes(stmt.body, scope))
            for handler in stmt.handlers:
                found.extend(_branch_outcomes(handler.body, scope))
            found.extend(_branch_outcomes(stmt.orelse, scope))
            found.extend(_branch_outcomes(stmt.finalbody, scope))
    return found


# --------------------------------------------------------------------------- scanning
@dataclass
class _FileScan:
    """Statement walker collecting coercions of protected kinds."""

    scope: _ModuleScope
    coercions: list[dict[str, Any]] = field(default_factory=list)
    guards: int = 0
    _seen: set[tuple[str, str, str, int]] = field(default_factory=set)

    def add(self, kind: str, label: str, pattern: str, line: int) -> None:
        key = (kind, label, pattern, line)
        if key in self._seen:
            return
        self._seen.add(key)
        self.coercions.append({"kind": kind, "mapped_to": label, "pattern": pattern, "line": line})

    # -- statements ------------------------------------------------------------------
    def scan_block(self, stmts: list[ast.stmt]) -> None:
        covered: set[str] = set()
        saw_guard = False
        for stmt in stmts:
            if isinstance(stmt, ast.If):
                chain_covered, chain_guarded = self.scan_if(stmt, set(), False)
                if chain_guarded:
                    saw_guard = True
                    covered |= chain_covered
            elif isinstance(stmt, ast.Return):
                if saw_guard and stmt.value is not None:
                    label = self.scope.binary_label(stmt.value)
                    if label is not None:
                        for kind in sorted(_PROTECTED - covered):
                            self.add(kind, label, "binary-fallthrough", stmt.lineno)
                self.scan_exprs(stmt)
            elif isinstance(stmt, ast.Match):
                self.scan_match(stmt)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.scan_block(stmt.body)
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                self.scan_exprs(stmt.iter)
                self.scan_block(stmt.body)
                self.scan_block(stmt.orelse)
            elif isinstance(stmt, ast.While):
                self.scan_exprs(stmt.test)
                self.scan_block(stmt.body)
                self.scan_block(stmt.orelse)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    self.scan_exprs(item.context_expr)
                self.scan_block(stmt.body)
            elif isinstance(stmt, ast.Try):
                self.scan_block(stmt.body)
                for handler in stmt.handlers:
                    self.scan_block(handler.body)
                self.scan_block(stmt.orelse)
                self.scan_block(stmt.finalbody)
            else:
                self.scan_exprs(stmt)

    def scan_if(
        self, node: ast.If, chain_covered: set[str], chain_guarded: bool
    ) -> tuple[set[str], bool]:
        """Scan one if/elif/else chain link; returns (kinds covered, chain had a kind guard)."""
        self.scan_exprs(node.test)
        guard = _parse_guard(node.test, self.scope)
        if guard is not None:
            self.guards += 1
            chain_guarded = True
            for label, via, line in _branch_outcomes(node.body, self.scope):
                pattern = "if-branch" if via == "return" else "if-branch-assign"
                for kind in sorted(guard.matched & _PROTECTED):
                    self.add(kind, label, pattern, line)
            chain_covered |= guard.matched
        elif chain_guarded:
            # An unguarded elif inside a kind-guarded chain behaves like a partial else.
            for label, _via, line in _branch_outcomes(node.body, self.scope):
                for kind in sorted(_PROTECTED - chain_covered):
                    self.add(kind, label, "binary-else", line)
        self.scan_block(node.body)
        orelse = node.orelse
        if not orelse:
            return chain_covered, chain_guarded
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            return self.scan_if(orelse[0], chain_covered, chain_guarded)
        if chain_guarded:
            for label, _via, line in _branch_outcomes(orelse, self.scope):
                for kind in sorted(_PROTECTED - chain_covered):
                    self.add(kind, label, "binary-else", line)
        self.scan_block(orelse)
        return chain_covered, chain_guarded

    def scan_match(self, node: ast.Match) -> None:
        self.scan_exprs(node.subject)
        if not self.scope.is_kind_expr(node.subject):
            for case in node.cases:
                self.scan_block(case.body)
            return
        covered: set[str] = set()
        for case in node.cases:
            kinds = self._pattern_kinds(case.pattern)
            if kinds is None:  # wildcard / capture: everything not yet covered lands here
                for label, _via, line in _branch_outcomes(case.body, self.scope):
                    for kind in sorted(_PROTECTED - covered):
                        self.add(kind, label, "match-case", line)
            else:
                self.guards += 1
                for label, _via, line in _branch_outcomes(case.body, self.scope):
                    for kind in sorted(kinds & _PROTECTED):
                        self.add(kind, label, "match-case", line)
                covered |= kinds
            self.scan_block(case.body)

    def _pattern_kinds(self, pattern: ast.pattern) -> frozenset[str] | None:
        if isinstance(pattern, ast.MatchValue):
            text = self.scope.string_of(pattern.value)
            return frozenset({text}) & ALL_KINDS if text is not None else frozenset()
        if isinstance(pattern, ast.MatchOr):
            out: frozenset[str] = frozenset()
            for sub in pattern.patterns:
                kinds = self._pattern_kinds(sub)
                if kinds is None:
                    return None
                out |= kinds
            return out
        if isinstance(pattern, ast.MatchAs):
            return None if pattern.pattern is None else self._pattern_kinds(pattern.pattern)
        return frozenset()

    # -- expressions -----------------------------------------------------------------
    def scan_exprs(self, node: ast.AST | None) -> None:
        """Find conditional-expression and dict-literal coercions anywhere under ``node``."""
        if node is None:
            return
        for sub in ast.walk(node):
            if isinstance(sub, ast.IfExp):
                self.scan_ifexp(sub)
            elif isinstance(sub, ast.Dict):
                self.scan_dict(sub)

    def scan_ifexp(self, node: ast.IfExp) -> None:
        guard = _parse_guard(node.test, self.scope)
        if guard is None:
            return
        self.guards += 1
        body_label = self.scope.binary_label(node.body)
        else_label = self.scope.binary_label(node.orelse)
        if body_label is not None:
            for kind in sorted(guard.matched & _PROTECTED):
                self.add(kind, body_label, "ifexp-binary", node.lineno)
        if else_label is not None:
            for kind in sorted(_PROTECTED - guard.matched):
                self.add(kind, else_label, "ifexp-else-binary", node.lineno)

    def scan_dict(self, node: ast.Dict) -> None:
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                continue
            key = self.scope.string_of(key_node)
            if key not in _PROTECTED:
                continue
            label = self.scope.binary_label(value_node)
            if label is not None:
                self.add(key, label, "dict-map", node.lineno)


def _mentions_and_reads(tree: ast.Module, scope: _ModuleScope) -> tuple[set[str], int]:
    """Kinds named anywhere in the file, and the number of structural kind reads."""
    mentions: set[str] = set()
    reads = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant, ast.Name, ast.Attribute)):
            text = scope.string_of(node)
            if text in ALL_KINDS:
                mentions.add(text)
        if scope.is_kind_expr(node):
            reads += 1
    return mentions, reads


# --------------------------------------------------------------------------- public API
def classify_file(path: str | Path) -> dict[str, Any]:
    """Statically classify one Python file as COERCES / PRESERVES / NO-KIND-READER / UNREADABLE.

    The returned row carries ``coercions`` (``kind``, ``mapped_to``, ``pattern``, ``line``),
    one ``handles_*`` flag per protected kind (``True`` when the reader never remaps it,
    ``False`` when it does, ``None`` when the file does not read kinds at all), the sorted
    ``mentions`` of kind constants, and the counts of structural ``kind_reads`` and ``guards``.
    """
    file_path = Path(path)
    row: dict[str, Any] = {
        "path": str(file_path),
        "role": "consumer",
        "classification": CLASS_UNREADABLE,
        "coercions": [],
        "handles_no_decision": None,
        "handles_conditional": None,
        "handles_proof": None,
        "mentions": [],
        "kind_reads": 0,
        "guards": 0,
    }
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=file_path.name)
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
        row["role"] = "unreadable"
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row

    scope = _ModuleScope(tree)
    scan = _FileScan(scope)
    scan.scan_block(tree.body)
    mentions, reads = _mentions_and_reads(tree, scope)

    coercions = sorted(scan.coercions, key=lambda c: (c["line"], c["kind"], c["pattern"], c["mapped_to"]))
    coerced = {c["kind"] for c in coercions}
    if coercions:
        classification = CLASS_COERCES
    elif mentions or scan.guards:
        # Names an outcome kind, or branches on the kind it reads, without collapsing any.
        classification = CLASS_PRESERVES
    else:
        # Reads of an unrelated ``kind`` field (event kinds, oracle kinds) are not outcome reads.
        classification = CLASS_NO_READER

    row.update(
        {
            "role": "consumer" if classification != CLASS_NO_READER else "non-reader",
            "classification": classification,
            "coercions": coercions,
            "mentions": sorted(mentions),
            "kind_reads": reads,
            "guards": scan.guards,
        }
    )
    for kind, field_name in _HANDLES_FIELD.items():
        row[field_name] = None if classification == CLASS_NO_READER else kind not in coerced
    return row


def _iter_python_files(paths: Iterable[str | Path] | str | Path) -> Iterator[tuple[Path, bool]]:
    """Yield ``(path, is_python)`` for every file the census should consider."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in sorted(p.rglob("*.py")):
                if "__pycache__" in child.parts:
                    continue
                yield child, True
        elif p.is_file():
            yield p, p.suffix == ".py"
        else:
            yield p, False


def census(paths: Iterable[str | Path] | str | Path) -> dict[str, Any]:
    """Run :func:`classify_file` over files and directories (recursively, ``*.py`` only).

    Returns the per-file ``rows`` plus the aggregate counts a gate needs: ``scanned``,
    ``skipped`` (non-Python or missing paths), ``coercers`` with ``coercer_paths``,
    ``preservers``, ``non_readers``, ``unreadable`` and ``coercions_by_kind``.
    """
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for file_path, is_python in _iter_python_files(paths):
        if not is_python:
            skipped.append(str(file_path))
            continue
        rows.append(classify_file(file_path))
    by_class = Counter(row["classification"] for row in rows)
    by_kind: Counter[str] = Counter()
    for row in rows:
        for coercion in row["coercions"]:
            by_kind[coercion["kind"]] += 1
    coercer_paths = [row["path"] for row in rows if row["classification"] == CLASS_COERCES]
    return {
        "protected_kinds": list(PROTECTED_KINDS),
        "binary_labels": sorted(BINARY_LABELS),
        "rows": rows,
        "scanned": len(rows),
        "skipped": len(skipped),
        "skipped_paths": skipped,
        "coercers": by_class.get(CLASS_COERCES, 0),
        "coercer_paths": coercer_paths,
        "preservers": by_class.get(CLASS_PRESERVES, 0),
        "non_readers": by_class.get(CLASS_NO_READER, 0),
        "unreadable": by_class.get(CLASS_UNREADABLE, 0),
        "coercions_by_kind": {kind: by_kind[kind] for kind in sorted(by_kind)},
    }


def count_kinds(items: Iterable[Any]) -> dict[str, int]:
    """Count outcome kinds over live artifacts.

    Each item may be an outcome object, a pipeline envelope (``{"outcome": {...}}``) or a
    path to a JSON file holding either. Binary aliases are refused with
    :class:`CollapseForbidden`; anything outside the closed kind set raises
    :class:`OutcomeValidationError`. The result is sorted by kind.
    """
    counts: Counter[str] = Counter()
    for item in items:
        if isinstance(item, (str, Path)):
            item = json.loads(Path(item).read_text(encoding="utf-8"))
        if isinstance(item, Mapping) and isinstance(item.get("outcome"), Mapping):
            item = item["outcome"]
        if not isinstance(item, Mapping):
            raise OutcomeValidationError("artifact is not an outcome object")
        value = str(item.get("kind") or "")
        if value.strip().upper() in BINARY_LABELS:
            raise CollapseForbidden(f"binary alias {value} is not a kind")
        if value not in ALL_KINDS:
            raise OutcomeValidationError(f"unknown kind {value!r}")
        counts[value] += 1
    return {kind: counts[kind] for kind in sorted(counts)}


def assert_coercer_caught(report: Mapping[str, Any] | list[dict[str, Any]], filename: str, kind: str) -> dict[str, Any]:
    """Assert that the census row for ``filename`` is COERCES with a coercion of ``kind``.

    ``report`` is a :func:`census` result or its ``rows`` list; ``filename`` is matched on
    its base name. Returns the matching row; raises :class:`AssertionError` otherwise.
    """
    rows = report.get("rows", []) if isinstance(report, Mapping) else list(report)
    target = Path(filename).name
    matches = [row for row in rows if Path(str(row.get("path", ""))).name == target]
    if not matches:
        raise AssertionError(f"{target} is not in the census ({len(rows)} rows scanned)")
    row = matches[0]
    if row.get("classification") != CLASS_COERCES:
        raise AssertionError(
            f"{target} classified {row.get('classification')}, expected {CLASS_COERCES}"
        )
    if not any(c.get("kind") == kind for c in row.get("coercions") or []):
        raise AssertionError(
            f"{target} was caught but no coercion is attributed to {kind}: {row.get('coercions')}"
        )
    return row


__all__ = [
    "ALL_KINDS",
    "BINARY_LABELS",
    "CLASS_COERCES",
    "CLASS_NO_READER",
    "CLASS_PRESERVES",
    "CLASS_UNREADABLE",
    "KIND_NAMES",
    "PROTECTED_KINDS",
    "assert_coercer_caught",
    "census",
    "classify_file",
    "count_kinds",
]
