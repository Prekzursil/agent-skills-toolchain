"""Static scan of the production invocation modules for shell-string spawns.

Walks the AST of the production launcher modules and flags any
``subprocess.*``/``os.system``/``os.popen`` call that passes ``shell=True`` or
builds its command by string concatenation/joining. The production surface
must be argv-array only; hits mean the TST-0191 property could be bypassed.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

PRODUCTION_FILES = (
    REPO / "lib" / "codex_invocation.py",
    REPO / "tools" / "lib" / "argv_echo.py",
)

_SPAWN_NAMES = {"run", "Popen", "call", "check_call", "check_output", "system", "popen"}


def _is_spawn_call(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in _SPAWN_NAMES:
        return func.attr
    if isinstance(func, ast.Name) and func.id in _SPAWN_NAMES:
        return func.id
    return None


def _first_arg_is_string_built(node: ast.Call) -> bool:
    if not node.args:
        return False
    arg = node.args[0]
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
        return True
    if isinstance(arg, ast.JoinedStr):
        return True
    if (
        isinstance(arg, ast.Call)
        and isinstance(arg.func, ast.Attribute)
        and arg.func.attr == "join"
    ):
        return True
    return False


def scan_file(path: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _is_spawn_call(node)
        if name is None:
            continue
        rel = path.relative_to(REPO).as_posix()
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                hits.append({"path": rel, "line": node.lineno, "call": name, "why": "shell=True"})
        if name in {"system", "popen"}:
            hits.append({"path": rel, "line": node.lineno, "call": name, "why": "os-shell-call"})
        if _first_arg_is_string_built(node):
            hits.append({"path": rel, "line": node.lineno, "call": name, "why": "string-built-command"})
    return hits


def scan_production() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    scanned: list[str] = []
    for path in PRODUCTION_FILES:
        if not path.is_file():
            continue
        scanned.append(path.relative_to(REPO).as_posix())
        hits.extend(scan_file(path))
    return {
        "ok": not hits,
        "hit_count": len(hits),
        "hits": hits,
        "scanned": scanned,
    }


__all__ = ["PRODUCTION_FILES", "scan_file", "scan_production"]
