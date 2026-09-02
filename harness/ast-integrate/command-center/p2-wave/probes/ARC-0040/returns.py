"""Enumerate adapter dispatch return points.

Catalog tests_required: no adapter code path may return without emitting
SUCCESS:<id> or FAILED:<id> <reason>, proven by enumerating the return
points. Detector-control: injecting `return None` into _checked must make
this checker fail.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ADAPTER = HERE / "adapter.py"
DISPATCH_FUNCS = frozenset({"dispatch", "_checked"})


def _is_marker_return(func_name: str, node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    if node.func.id == "terminal":
        return True
    # dispatch delegates to _checked; _checked is itself enumerated.
    return func_name == "dispatch" and node.func.id == "_checked"


def enumerate_dispatch_returns(src: str) -> list[dict[str, Any]]:
    tree = ast.parse(src)
    rows: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in DISPATCH_FUNCS:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Return):
                continue
            via_terminal = child.value is not None and _is_marker_return(
                node.name, child.value
            )
            rows.append(
                {
                    "function": node.name,
                    "lineno": child.lineno,
                    "via_terminal": via_terminal,
                    "snippet": ast.get_source_segment(src, child) or "",
                }
            )
    rows.sort(key=lambda r: (r["function"], r["lineno"]))
    return rows


def dispatch_returns_are_terminal(src: str) -> tuple[bool, str]:
    rows = enumerate_dispatch_returns(src)
    if not rows:
        return False, "no-dispatch-returns"
    funcs = {r["function"] for r in rows}
    if funcs != DISPATCH_FUNCS:
        return False, f"funcs={sorted(funcs)}"
    bad = [r for r in rows if not r["via_terminal"]]
    if bad:
        return False, f"unmarked:{bad[0]['function']}:{bad[0]['lineno']}"
    if len(rows) < 6:
        return False, f"too-few-return-points:{len(rows)}"
    return True, f"return_points={len(rows)}"


def mutant_unmarked_return_is_caught(src: str) -> bool:
    needle = "def _checked(request: dict, uid: str) -> dict:\n"
    if needle not in src:
        return False
    mutated = src.replace(needle, needle + "    return None\n", 1)
    ok, _ = dispatch_returns_are_terminal(mutated)
    return ok is False


def live_report() -> dict[str, Any]:
    src = ADAPTER.read_text(encoding="utf-8")
    rows = enumerate_dispatch_returns(src)
    ok, why = dispatch_returns_are_terminal(src)
    caught = mutant_unmarked_return_is_caught(src)
    return {
        "pass": bool(ok and caught),
        "why": why,
        "mutant_unmarked_caught": caught,
        "return_points": rows,
        "return_point_count": len(rows),
        "functions": sorted(DISPATCH_FUNCS),
    }
