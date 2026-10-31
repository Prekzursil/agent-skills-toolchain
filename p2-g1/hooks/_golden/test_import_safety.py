#!/usr/bin/env python3
"""Both golden acceptance files must be IMPORTABLE without exiting the interpreter.

A ``sys.exit`` that runs at import time escapes during pytest COLLECTION as
``SystemExit``, which pytest reports as ``INTERNALERROR`` and which aborts the ENTIRE
run -- not merely the offending file.  ``agent-self/config/hooks/_golden/test_hooks.py``
did exactly that: it executed five acceptance probes at module scope and then called
``sys.exit`` unconditionally, so a recursive ``pytest`` over that tree collected **zero**
tests and took its ~148 collectable ``wearables/`` siblings down with it.  The canonical
top-level ``hooks/_golden/test_hooks.py`` was repaired earlier (its work is inside
``main()``); the deployed snapshot that ``agent-self/bootstrap.ps1`` copies into
``~/.claude`` was not, so this pins BOTH.

This suite is collected by the whole-tree ``python -m pytest hooks/`` step in
.github/workflows/quality.yml, so it needs no separate named step.

Scope note, deliberately narrow: ``cmd-rewrite/test_hooks.py`` and
``memory-guard/test_scan.py`` DO still exit at import time in both trees.  That is the
repo's accepted design for them -- quality.yml ``--ignore``s exactly those two and runs
them as standalone scripts instead -- so they are excluded here rather than "fixed".
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
HOOKS_ROOT = HERE.parent
REPO_ROOT = HOOKS_ROOT.parent

CANONICAL_GOLDEN = HERE / "test_hooks.py"
SNAPSHOT_GOLDEN = (
    REPO_ROOT / "agent-self" / "config" / "hooks" / "_golden" / "test_hooks.py"
)
GOLDEN_FILES = (
    ("canonical hooks/ tree", CANONICAL_GOLDEN),
    ("agent-self deploy snapshot", SNAPSHOT_GOLDEN),
)

# A module-scope statement of one of these kinds does not execute on import.
_DEFERRED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

_KNOWN_BROKEN_SOURCE = "import sys\nprint('checks ran')\nsys.exit(1)\n"
_KNOWN_FIXED_SOURCE = (
    "import sys\n\n\ndef main():\n    return 0\n\n\n"
    'if __name__ == "__main__":\n    sys.exit(main())\n'
)


def _is_main_guard(node: ast.stmt) -> bool:
    """True for ``if __name__ == "__main__":`` -- false during an import."""

    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    left, right = test.left, test.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    )


def _exit_call_lines(node: ast.AST) -> list[int]:
    lines: list[int] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name == "exit":
            lines.append(sub.lineno)
    return lines


def import_time_exit_lines(source: str) -> list[int]:
    """Lines whose ``sys.exit``/``exit`` call fires when the module is merely imported."""

    lines: list[int] = []
    for node in ast.parse(source).body:
        if isinstance(node, _DEFERRED) or _is_main_guard(node):
            continue
        lines.extend(_exit_call_lines(node))
    return sorted(lines)


def test_detector_fires_on_the_known_broken_shape_and_not_the_fixed_one():
    """Control the detector first -- a probe silent in BOTH states measures nothing.

    Without this, every assertion below would pass just as happily against a detector
    that never fires (e.g. one that walked only ``ast.Expr`` nodes, or that descended
    into the ``__main__`` guard and so flagged every correctly-guarded file).
    """

    assert import_time_exit_lines(_KNOWN_BROKEN_SOURCE) == [3]
    assert import_time_exit_lines(_KNOWN_FIXED_SOURCE) == []


@pytest.mark.parametrize(
    "label,path", GOLDEN_FILES, ids=[label for label, _ in GOLDEN_FILES]
)
def test_golden_acceptance_file_has_no_import_time_exit(label: str, path: Path):
    assert path.is_file(), f"{label}: expected a golden acceptance file at {path}"
    source = path.read_text(encoding="utf-8")
    offenders = import_time_exit_lines(source)
    assert not offenders, (
        f"{label}: {path.name} calls sys.exit at import time (line(s) {offenders}). "
        "pytest raises SystemExit during collection and reports INTERNALERROR, which "
        "aborts the whole run. Move the work into main() and guard the exit with "
        'if __name__ == "__main__".'
    )
    assert any(_is_main_guard(node) for node in ast.parse(source).body), (
        f"{label}: {path.name} must keep its standalone entry point behind an "
        'if __name__ == "__main__" guard'
    )


@pytest.mark.parametrize(
    "label,path", GOLDEN_FILES, ids=[label for label, _ in GOLDEN_FILES]
)
def test_golden_acceptance_file_imports_without_running_its_checks(
    label: str, path: Path
):
    """The operation pytest performs during collection, done for real.

    Loaded under a unique synthetic module name: the two files share the basename
    ``test_hooks.py``, so a shared ``sys.modules`` key would make whichever imported
    first decide what the other one "is".
    """

    unique = "c47_golden_" + label.replace(" ", "_").replace("/", "_").replace("-", "_")
    spec = importlib.util.spec_from_file_location(unique, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit as exc:  # pragma: no cover - the regression this file guards
        pytest.fail(f"{label}: importing {path.name} raised SystemExit({exc.code})")
    assert callable(getattr(module, "main", None)), (
        f"{label}: {path.name} must expose a callable main() once the module-scope "
        "work is moved out of import"
    )
