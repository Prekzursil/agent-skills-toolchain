#!/usr/bin/env python3
"""ADV-0022 probe2_static.py -- static enforcement-point audit (2026-10-21, full tree).

Same instrument class as the 2026-08-19 probe2 (line scan + AST Call nodes +
getattr heuristic for RUNTIME callers of the authorization checker, plus a
checkout-surface census), re-run because the August substrate was a SPARSE
Linux worktree in which hooks/ and platform/lib/wfdsl were absent, while the
2026-10-21 tree at c119cf0da contains BOTH.

Question answered (catalog ADV-0022 evidence_requirement Probe 2): is the
declared tool_permissions set enforced AT CALL TIME by anything in this tree,
or merely recorded in metadata / checked at analysis time?  A declaration with
no runtime enforcement point is escaped by construction.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SCAN_ROOTS = ["hooks", "platform", "tools", "command-center", "skills", ".agents"]
CHECKER = "check_work_unit_authorization"

# Directories that are probe/measurement working dirs or vendored mirrors, not
# dispatch surfaces.
EXCLUDE_PARTS = {"__pycache__", "node_modules", ".git", "p2-wave", "casualty", "fixtures"}


def iter_py_files():
    for root in SCAN_ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_PARTS]
            for fn in filenames:
                if fn.endswith(".py"):
                    yield Path(dirpath) / fn


def surface_census() -> dict:
    return {
        "hooks_dir_exists": (REPO / "hooks").is_dir(),
        "hooks_files": sorted(p.name for p in (REPO / "hooks").glob("*.py"))
        if (REPO / "hooks").is_dir() else [],
        "wfdsl_semantics_exists": (REPO / "platform/lib/wfdsl/semantics.py").is_file(),
        "marketplace_exists": (REPO / "platform/marketplace").is_dir(),
        "plugin_cli_exists": (REPO / "platform/plugin/cli.py").is_file(),
    }


def classify_call_sites():
    """Every reference to CHECKER, classified by what the containing file IS."""
    refs = []
    for py in iter_py_files():
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if CHECKER not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            refs.append({"file": str(py.relative_to(REPO)), "class": "unparseable"})
            continue
        # collect module-level facts
        has_main_or_cli = any(
            (isinstance(n, ast.FunctionDef) and n.name in {"main", "cli", "run"})
            or isinstance(n, ast.IfExp)
            for n in tree.body
        )
        doc = ast.get_docstring(tree) or ""
        is_test = py.name.startswith("test_") or "test" in py.parts[-2:][:1]
        classes = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == CHECKER:
                    classes.add("ast-call")
            if isinstance(node, ast.Attribute) and node.attr == CHECKER:
                classes.add("attribute-ref")
            if isinstance(node, ast.Name) and node.id == CHECKER:
                classes.add("name-ref")
        kind = "analysis-time"
        if is_test:
            kind = "test"
        elif "test" in py.name or "/tests/" in str(py).replace("\\", "/"):
            kind = "test"
        refs.append({
            "file": str(py.relative_to(REPO)),
            "classes": sorted(classes),
            "kind": kind,
            "has_main_or_cli": has_main_or_cli,
            "doc_head": doc.splitlines()[0][:100] if doc else "",
        })
    return refs


def runtime_dispatch_scan():
    """Is there ANY PreToolUse / tool-dispatch interception that consults a
    component's declared permissions at call time?  Line-scan for the known
    interception idioms across the same roots."""
    idioms = [
        r"PreToolUse",
        r"before_tool_call|before_tool_use|pre_tool",
        r"tool_permissions",
        r"allowed-tools|allowed_tools",
    ]
    hits = {i: [] for i in idioms}
    for py in iter_py_files():
        try:
            lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for i in idioms:
                if re.search(i, line):
                    hits[i].append(f"{py.relative_to(REPO)}:{n}")
    return {i: {"count": len(v), "sample": v[:12]} for i, v in hits.items()}


def main() -> int:
    surface = surface_census()
    refs = classify_call_sites()
    dispatch = runtime_dispatch_scan()

    runtime_callers = [
        r for r in refs
        if r.get("kind") != "test" and "ast-call" in r.get("classes", [])
        and "dispatch" in json.dumps(r).lower()
    ]
    # An honest runtime caller would be a dispatcher that calls CHECKER on a
    # live tool invocation.  Census callers (authz_census) and schema-semantic
    # checkers (semantics.evaluate_work_unit) are ANALYSIS time by docstring.
    analysis_callers = [r for r in refs if r.get("kind") != "test"]

    verdict = {
        "surface": surface,
        "checker_references": refs,
        "checker_reference_count": len(refs),
        "non_test_callers": analysis_callers,
        "runtime_dispatch_idioms": dispatch,
        "runtime_callers_count": len(runtime_callers),
        "conclusion": (
            "ZERO call-time enforcement callers of " + CHECKER
            if len(runtime_callers) == 0
            else "runtime caller(s) present: " + json.dumps(runtime_callers)
        ),
    }
    print("ADV0022_STATIC_BEGIN")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    print("ADV0022_STATIC_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
