"""Shared IMP-0136 probe helpers."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SPEC_ROOT = REPO / "tools" / "agentspec"
DISPATCH_PY = SPEC_ROOT / "agentspec" / "dispatchpolicy.py"

if str(SPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(SPEC_ROOT))


def dispatch_source() -> str:
    return DISPATCH_PY.read_text(encoding="utf-8")


def authorize_before_spawn(src: str | None = None) -> bool:
    """True iff dispatch() calls authorize before _call_spawn."""
    tree = ast.parse(src if src is not None else dispatch_source())
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "dispatch":
            continue
        names: list[str] = []
        for stmt in node.body:
            for call in ast.walk(stmt):
                if not isinstance(call, ast.Call):
                    continue
                func = call.func
                if isinstance(func, ast.Name):
                    names.append(func.id)
        if "authorize" not in names or "_call_spawn" not in names:
            return False
        return names.index("authorize") < names.index("_call_spawn")
    return False


def mutate_check_after_spawn(src: str) -> ast.Module:
    tree = ast.parse(src)
    found = False
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "dispatch":
            continue
        if len(node.body) != 2:
            raise AssertionError(
                f"dispatch() body must be authorize + return spawn, got {len(node.body)}"
            )
        authorize_stmt, return_stmt = node.body
        if not isinstance(return_stmt, ast.Return) or return_stmt.value is None:
            raise AssertionError("dispatch() must return _call_spawn(...)")
        node.body = [
            ast.Assign(
                targets=[ast.Name(id="result", ctx=ast.Store())],
                value=return_stmt.value,
            ),
            authorize_stmt,
            ast.Return(value=ast.Name(id="result", ctx=ast.Load())),
        ]
        found = True
        break
    if not found:
        raise AssertionError("dispatch() not found")
    return ast.fix_missing_locations(tree)
