"""A STATIC CHECK over this package's own source: no wall clock, no entropy.

Regression row R8 says two runs of the same spec must produce identical artifacts. Coverage
cannot prove that — a `time.time()` call is happily covered. So the property is asserted
structurally: :func:`scan_package` walks this package and fails on any forbidden import or
call, and ``tests/test_determinism.py`` validates the detector against a known-broken fixture
for EVERY forbidden form before trusting its silence on the real tree.

Time enters through the injected :class:`agentspec.clock.Clock` port instead, which is why
``clock.now_ms()`` is deliberately NOT flagged (there is a detector control for that too — a
guard that blocks the sanctioned path is as broken as one that misses the banned path).

This module reads files, so it is not itself "pure"; it is a build-time analyser, never on the
dispatch path.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_MODULES: tuple[str, ...] = ("datetime", "random", "secrets", "time", "uuid")
"""Root package names whose import is banned. An alias (``import time as t``) is still caught,
because the check reads the MODULE name, not the binding."""

FORBIDDEN_NAMES: tuple[str, ...] = (
    "getrandbits",
    "monotonic",
    "monotonic_ns",
    "perf_counter",
    "perf_counter_ns",
    "time_ns",
    "urandom",
    "utcnow",
    "uuid1",
    "uuid3",
    "uuid4",
    "uuid5",
)
"""Callable names that exist ONLY as a clock or entropy source, so a bare or attribute call to
one is banned regardless of how it was imported (this is what catches ``os.urandom``, whose
module is legitimately allowed)."""


@dataclass(frozen=True, slots=True)
class Finding:
    """One violation: where it is, which rule it broke, and what was seen."""

    path: str
    line: int
    code: str
    detail: str


def scan_source(source: str, path: str) -> tuple[Finding, ...]:
    """Scan one module's text. An unparseable module is a FINDING, never a silent skip."""
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
    findings: list[Finding] = []
    for node in ast.walk(tree):
        findings.extend(_check_node(node, path))
    return tuple(sorted(findings, key=lambda f: (f.line, f.code, f.detail)))


def package_files(root: Path) -> tuple[Path, ...]:
    """Every ``*.py`` under ``root``, sorted. Exposed so a test can prove the walk is not empty
    — an empty walk reports zero findings and would otherwise read as a pass."""
    return tuple(sorted(root.rglob("*.py")))


def scan_package(root: Path) -> tuple[Finding, ...]:
    """Scan every module under ``root``, ordered by relative path then line."""
    findings: list[Finding] = []
    for file in package_files(root):
        rel = file.relative_to(root).as_posix()
        try:
            source = file.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            findings.append(
                Finding(path=rel, line=1, code="read-error", detail=f"cannot read: {exc.reason}")
            )
            continue
        findings.extend(scan_source(source, rel))
    return tuple(sorted(findings, key=lambda f: (f.path, f.line, f.code)))


def _check_node(node: ast.AST, path: str) -> Iterable[Finding]:
    if isinstance(node, ast.Import):
        return _check_import(node, path)
    if isinstance(node, ast.ImportFrom):
        return _check_import_from(node, path)
    if isinstance(node, ast.Call):
        return _check_call(node, path)
    return ()


def _check_import(node: ast.Import, path: str) -> list[Finding]:
    findings: list[Finding] = []
    for alias in node.names:
        if _root(alias.name) in FORBIDDEN_MODULES:
            findings.append(
                Finding(
                    path=path,
                    line=node.lineno,
                    code="forbidden-import",
                    detail=f"import {alias.name}",
                )
            )
    return findings


def _check_import_from(node: ast.ImportFrom, path: str) -> list[Finding]:
    findings: list[Finding] = []
    module = node.module or ""
    if _root(module) in FORBIDDEN_MODULES:
        findings.append(
            Finding(
                path=path,
                line=node.lineno,
                code="forbidden-import",
                detail=f"from {module} import ...",
            )
        )
    for alias in node.names:
        if alias.name in FORBIDDEN_NAMES:
            findings.append(
                Finding(
                    path=path,
                    line=node.lineno,
                    code="forbidden-import-name",
                    detail=f"from {module} import {alias.name}",
                )
            )
    return findings


def _check_call(node: ast.Call, path: str) -> list[Finding]:
    name = _called_name(node.func)
    if name in FORBIDDEN_NAMES:
        return [
            Finding(
                path=path, line=node.lineno, code="forbidden-call", detail=f"call to {name}()"
            )
        ]
    return []


def _called_name(func: ast.expr) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _root(dotted: str) -> str:
    return dotted.split(".", 1)[0]
