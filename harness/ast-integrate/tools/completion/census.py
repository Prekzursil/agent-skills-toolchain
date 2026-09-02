"""Import-graph census for the shared reducer.

Detects local completion predicates — an ``exit_code == 0`` compare mapped to
a COMPLETE verdict, or a local ``judge`` definition — and records whether a
site imported ``completion.reducer.judge``. Two mechanically different
detectors (AST and regex) exist so a reviewer can re-run the census with a
pattern the author did not write.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from completion.reducer import LIBRARY, judge


def _rel(path: Path, root: Path | None) -> str:
    p = Path(path)
    if root is not None:
        try:
            return p.resolve().relative_to(Path(root).resolve()).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix()


def _mentions_exit_code(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "exit_code":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "exit_code":
            return True
        if isinstance(sub, ast.Constant) and sub.value == "exit_code":
            return True
    return False


def _is_exit_zero_compare(node: ast.Compare) -> bool:
    if not _mentions_exit_code(node.left):
        return False
    for op, comparator in zip(node.ops, node.comparators):
        if isinstance(op, ast.Eq) and isinstance(comparator, ast.Constant) and comparator.value == 0:
            return True
    return False


def _returns_complete(fn: ast.AST) -> bool:
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Return) and sub.value is not None:
            for leaf in ast.walk(sub.value):
                if isinstance(leaf, ast.Constant) and leaf.value == "COMPLETE":
                    return True
    return False


def _ast_hits(text: str, rel: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    hits: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            exit_zero = any(
                isinstance(sub, ast.Compare) and _is_exit_zero_compare(sub)
                for sub in ast.walk(node)
            )
            if node.name == "judge":
                hits.append(
                    {
                        "kind": "local-judge-def",
                        "path": rel,
                        "function": node.name,
                        "library": "local-copy",
                        "shared_library": LIBRARY,
                        "judge_name": judge.__name__,
                    }
                )
            if exit_zero:
                hits.append(
                    {
                        "kind": "exit-zero-compare",
                        "path": rel,
                        "function": node.name,
                        "detector": "ast",
                        "note": "exit_code == 0 used as a completion predicate",
                    }
                )
                if _returns_complete(node):
                    hits.append(
                        {
                            "kind": "local-complete-return",
                            "path": rel,
                            "function": node.name,
                            "detector": "ast",
                            "note": "COMPLETE returned locally instead of via judge",
                        }
                    )
    return hits


_EXIT_ZERO_RE = re.compile(r"exit_code[\"'\)\s\]]*\s*==\s*0")


def _regex_hits(text: str, rel: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if _EXIT_ZERO_RE.search(text) and "COMPLETE" in text:
        hits.append(
            {
                "kind": "exit-zero-regex",
                "path": rel,
                "detector": "regex",
                "note": "exit_code == 0 co-occurring with COMPLETE",
            }
        )
    return hits


def census_file(path: Path, root: Path | None = None, detector: str = "ast") -> list[dict[str, Any]]:
    """Return local-predicate hits. Empty for shared-reducer call sites."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rel = _rel(Path(path), root)
    if detector == "regex":
        return _regex_hits(text, rel)
    return _ast_hits(text, rel)


def census_dir(base: Path, root: Path | None = None, detector: str = "ast", **kwargs: Any) -> list[dict[str, Any]]:
    del kwargs
    hits: list[dict[str, Any]] = []
    base = Path(base)
    if not base.exists():
        return hits
    rel_root = root if root is not None else (base if base.is_dir() else base.parent)
    files = [base] if base.is_file() else sorted(p for p in base.rglob("*.py") if p.is_file())
    for path in files:
        hits.extend(census_file(path, root=rel_root, detector=detector))
    return hits


def import_graph_site(path: Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {
            "path": str(path),
            "imports": [],
            "ok": False,
            "imported_judge": False,
            "calls_judge": False,
        }
    imports: list[str] = []
    imported_judge = False
    calls_judge = False
    judge_aliases = {"judge"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            if node.module.startswith("completion"):
                for alias in node.names:
                    if alias.name == "judge":
                        imported_judge = True
                        judge_aliases.add(alias.asname or "judge")
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in judge_aliases:
                calls_judge = True
            elif isinstance(fn, ast.Attribute) and fn.attr == "judge":
                calls_judge = True
    uses_shared = any(name.startswith("completion") for name in imports)
    return {
        "path": str(path),
        "imports": imports,
        "uses_shared": uses_shared,
        "imported_judge": imported_judge or uses_shared,
        "calls_judge": calls_judge or imported_judge,
        "ok": True,
    }
