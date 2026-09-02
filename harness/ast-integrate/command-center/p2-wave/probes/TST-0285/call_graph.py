"""Call-graph checks for TST-0285: shared reducer at sibling fan-in."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
COC = REPO / "tools" / "council" / "topology" / "coc.py"
TARGET_FN = "_judge_sibling_boundary"
REQUIRED_CALL = "shared_judge"


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _call_names(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def sibling_boundary_calls_shared_reducer(source: str | None = None) -> dict[str, Any]:
    text = source if source is not None else COC.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = _fn(tree, TARGET_FN)
    if fn is None:
        return {
            "ok": False,
            "reason": f"missing-function:{TARGET_FN}",
            "calls": [],
            "path": str(COC.relative_to(REPO).as_posix()),
        }
    calls = sorted(_call_names(fn))
    ok = REQUIRED_CALL in _call_names(fn)
    return {
        "ok": ok,
        "reason": "shared_judge-called" if ok else "shared_judge-absent",
        "function": TARGET_FN,
        "calls": calls,
        "path": str(COC.relative_to(REPO).as_posix()),
    }


def fan_in_cites_shared_judge(source: str | None = None) -> dict[str, Any]:
    text = source if source is not None else COC.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = _fn(tree, "fan_in")
    if fn is None:
        return {"ok": False, "reason": "missing-function:fan_in"}
    calls = _call_names(fn)
    ok = TARGET_FN in calls and "_judge_parent_after_fanin" in calls
    return {
        "ok": ok,
        "reason": "fan_in-calls-boundary-and-parent-judges" if ok else "fan_in-missing-judges",
        "calls": sorted(calls),
    }


def mutant_drops_reducer() -> dict[str, Any]:
    original = COC.read_text(encoding="utf-8")
    tree = ast.parse(original)
    fn = _fn(tree, TARGET_FN)
    if fn is None:
        return {"ok": False, "reason": "missing-function"}
    fn.body = [
        ast.Return(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="artifact", ctx=ast.Load()),
                    attr="get",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value="self_report_complete")],
                keywords=[],
            )
        )
    ]
    ast.fix_missing_locations(tree)
    mutant_src = ast.unparse(tree)
    live = sibling_boundary_calls_shared_reducer(original)
    planted = sibling_boundary_calls_shared_reducer(mutant_src)
    fires = live["ok"] is True and planted["ok"] is False
    return {
        "ok": fires,
        "live_ok": live["ok"],
        "planted_ok": planted["ok"],
        "reason": (
            "detector-fires-on-rival-predicate"
            if fires
            else "detector-silent-on-rival"
        ),
    }
