"""AST import-graph: three call sites import the same reducer and call it."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REDUCER_MOD = "tools.foundry.completion_predicate"
REQUIRED_CALL = "evaluate"
SITES = (
    ("local-runner", "tools/foundry/local_runner.py", "certify_workflow"),
    ("tournament-runner", "tools/foundry/tournament_runner.py", "certify_workflow"),
    ("certification-gate", "tools/foundry/certification_gate.py", "certify_workflow"),
)


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


def _imported_evaluate(tree: ast.AST) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == REDUCER_MOD:
            aliases = [a.name for a in node.names]
            hits.append(
                {
                    "module": node.module,
                    "names": aliases,
                    "lineno": node.lineno,
                    "has_evaluate": "evaluate" in aliases,
                }
            )
    return {
        "ok": any(h["has_evaluate"] for h in hits),
        "imports": hits,
    }


def inspect_site(rel: str, fn_name: str, source: str | None = None) -> dict[str, Any]:
    path = REPO / rel
    text = source if source is not None else path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = _imported_evaluate(tree)
    fn = _fn(tree, fn_name)
    if fn is None:
        return {
            "ok": False,
            "path": rel,
            "reason": f"missing-function:{fn_name}",
            "import_ok": imported["ok"],
            "imports": imported["imports"],
            "calls": [],
        }
    calls = sorted(_call_names(fn))
    calls_evaluate = REQUIRED_CALL in _call_names(fn)
    ok = imported["ok"] and calls_evaluate
    reason = "shared-reducer-imported-and-called"
    if not imported["ok"]:
        reason = "reducer-import-absent"
    elif not calls_evaluate:
        reason = "evaluate-not-called"
    return {
        "ok": ok,
        "path": rel,
        "function": fn_name,
        "function_lineno": fn.lineno,
        "reason": reason,
        "import_ok": imported["ok"],
        "imports": imported["imports"],
        "calls": calls,
        "calls_evaluate": calls_evaluate,
        "reducer_module": REDUCER_MOD,
    }


def graph() -> dict[str, Any]:
    sites = []
    for locus, rel, fn in SITES:
        row = inspect_site(rel, fn)
        row["locus"] = locus
        sites.append(row)
    modules = sorted(
        {
            imp["module"]
            for site in sites
            for imp in site.get("imports") or []
            if imp.get("has_evaluate")
        }
    )
    ok = all(s["ok"] for s in sites) and modules == [REDUCER_MOD]
    return {
        "ok": ok,
        "reducer_module": REDUCER_MOD,
        "imported_modules": modules,
        "same_module": modules == [REDUCER_MOD],
        "sites": sites,
        "reason": (
            "three-sites-one-reducer"
            if ok
            else "import-graph-refute"
        ),
    }


def mutant_drops_reducer() -> dict[str, Any]:
    """Plant a rival local predicate at the certification gate. Detector must fire."""
    rel = "tools/foundry/certification_gate.py"
    original = (REPO / rel).read_text(encoding="utf-8")
    tree = ast.parse(original)
    fn = _fn(tree, "certify_workflow")
    if fn is None:
        return {"ok": False, "reason": "missing-function"}
    fn.body = [
        ast.Return(
            value=ast.Constant(value=True),
        )
    ]
    ast.fix_missing_locations(tree)
    mutant_src = ast.unparse(tree)
    live = inspect_site(rel, "certify_workflow", original)
    planted = inspect_site(rel, "certify_workflow", mutant_src)
    fires = live["ok"] is True and planted["ok"] is False
    return {
        "ok": fires,
        "live_ok": live["ok"],
        "planted_ok": planted["ok"],
        "planted_reason": planted["reason"],
        "reason": (
            "detector-fires-on-rival-predicate"
            if fires
            else "detector-silent-on-rival"
        ),
    }
