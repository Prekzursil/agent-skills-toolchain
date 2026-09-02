"""Call-graph checks for IMP-0288: shared reducer at the child boundary."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
NESTED = REPO / "tools" / "council" / "topology" / "nested.py"
TARGET_FN = "_judge_at_child_boundary"
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


def child_boundary_calls_shared_reducer(source: str | None = None) -> dict[str, Any]:
    text = source if source is not None else NESTED.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = _fn(tree, TARGET_FN)
    if fn is None:
        return {
            "ok": False,
            "reason": f"missing-function:{TARGET_FN}",
            "calls": [],
        }
    calls = sorted(_call_names(fn))
    ok = REQUIRED_CALL in _call_names(fn)
    return {
        "ok": ok,
        "reason": "shared_judge-called" if ok else "shared_judge-absent",
        "function": TARGET_FN,
        "calls": calls,
        "path": str(NESTED.relative_to(REPO).as_posix()),
    }


def mutant_drops_reducer() -> dict[str, Any]:
    """Plant a rival local predicate. The call-graph check MUST fire."""
    original = NESTED.read_text(encoding="utf-8")
    tree = ast.parse(original)
    fn = _fn(tree, TARGET_FN)
    if fn is None:
        return {"ok": False, "reason": "missing-function"}
    # return artifact.get("self_report_complete")  — rival predicate
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
    live = child_boundary_calls_shared_reducer(original)
    planted = child_boundary_calls_shared_reducer(mutant_src)
    fires = live["ok"] is True and planted["ok"] is False
    return {
        "ok": fires,
        "live_ok": live["ok"],
        "planted_ok": planted["ok"],
        "reason": "detector-fires-on-rival-predicate"
        if fires
        else "detector-silent-on-rival",
    }


def resolution_rule_is_named(source: str | None = None) -> dict[str, Any]:
    text = source if source is not None else NESTED.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = _fn(tree, "resolve_disagreement")
    if fn is None:
        return {"ok": False, "reason": "missing-resolve_disagreement"}
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            names.add(node.id)
    ok = "RESOLUTION_RULE_ID" in names
    return {
        "ok": ok,
        "reason": "rule-id-referenced" if ok else "rule-id-absent",
        "names_sample": sorted(names)[:20],
    }
