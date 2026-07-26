"""ASSERTION-DENSITY LINT — anti-coverage-theatre layer 2, as a real check.

A test function with zero assertions executes lines and asserts nothing. It raises coverage
without protecting behaviour, and it is invisible to a whole-file mutation guard: the file
still exits non-zero on every mutant because its strong siblings kill them. Discharging this
requirement with the sentence "satisfied structurally by the mutation guard" was a measured
overclaim, so this is an AST pass with both-states fixtures.

What counts as an assertion, in the body of a ``test_*`` function:

* an ``assert`` statement;
* a ``with pytest.raises(...)`` / ``pytest.warns(...)`` block;
* a call whose name starts with ``assert`` (``assertEqual``, ``assert_frame_equal``).

A nested ``def`` inside the test does NOT launder an assertion: the checker only counts
assertions in the test's own body, so hiding the only assert in an uncalled inner function
still reports the test as assertion-free.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from agentspec.determinism import Finding

_RAISES_HELPERS: tuple[str, ...] = ("raises", "warns")

TestFn = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True, slots=True)
class _Counted:
    """Internal tally so the walk stays readable."""

    assertions: int


def scan_test_source(source: str, path: str) -> tuple[Finding, ...]:
    """Scan one test module's text. An unparseable module is a FINDING, never a skip."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return (
            Finding(
                path=path,
                line=exc.lineno or 1,
                code="unparseable",
                detail=f"cannot parse: {exc.msg}",
            ),
        )
    findings = [
        Finding(
            path=path,
            line=fn.lineno,
            code="no-assertion",
            detail=f"{fn.name} has no assertion",
        )
        for fn in _test_functions(tree)
        if _count_assertions(fn).assertions == 0
    ]
    return tuple(sorted(findings, key=lambda f: f.line))


def test_files(root: Path) -> tuple[Path, ...]:
    """Every ``test_*.py`` under ``root``, sorted. Exposed so a test can prove the walk is not
    empty — an empty walk reports zero findings and would otherwise read as a pass."""
    return tuple(sorted(root.rglob("test_*.py")))


def scan_tests(root: Path) -> tuple[Finding, ...]:
    """Scan every test module under ``root``, ordered by relative path then line."""
    findings: list[Finding] = []
    for file in test_files(root):
        rel = file.relative_to(root).as_posix()
        try:
            source = file.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            findings.append(
                Finding(path=rel, line=1, code="read-error", detail=f"cannot read: {exc.reason}")
            )
            continue
        findings.extend(scan_test_source(source, rel))
    return tuple(sorted(findings, key=lambda f: (f.path, f.line)))


def _test_functions(tree: ast.Module) -> list[TestFn]:
    """Every ``test_*`` function, whether module-level or a method on a class."""
    found: list[TestFn] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            found.append(node)
    return found


def _count_assertions(fn: TestFn) -> _Counted:
    """Count assertions in ``fn``'s OWN body, not inside a nested function definition."""
    total = 0
    for node in _own_body(fn):
        if isinstance(node, ast.Assert):
            total += 1
        elif isinstance(node, ast.With | ast.AsyncWith):
            total += _count_context_assertions(node)
        elif isinstance(node, ast.Call) and _is_assert_call(node):
            total += 1
    return _Counted(assertions=total)


def _own_body(fn: TestFn) -> list[ast.AST]:
    """Walk ``fn``'s body but do not descend into a nested function or class definition."""
    collected: list[ast.AST] = []
    pending: list[ast.AST] = list(fn.body)
    while pending:
        node = pending.pop()
        collected.append(node)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        pending.extend(ast.iter_child_nodes(node))
    return collected


def _count_context_assertions(node: ast.With | ast.AsyncWith) -> int:
    total = 0
    for item in node.items:
        expr = item.context_expr
        if (
            isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Attribute)
            and expr.func.attr in _RAISES_HELPERS
        ):
            total += 1
    return total


def _is_assert_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr.startswith("assert")
    if isinstance(func, ast.Name):
        return func.id.startswith("assert")
    return False
