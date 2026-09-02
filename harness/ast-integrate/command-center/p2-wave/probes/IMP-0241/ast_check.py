#!/usr/bin/env python3
"""AST assertion: release-go-no-go calls oracle.judge, not a local checklist."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

RIVAL_LOCAL_CHECKLIST = '''
def release_go_no_go(evidence):
    checklist = [
        evidence.get("tests_passed"),
        evidence.get("artifact_exists"),
        evidence.get("exit_code") == 0,
    ]
    return "GO" if all(checklist) else "NO-GO"
'''


def _call_attr(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _imports_oracle_judge(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            tail = mod.split(".")[-1]
            if tail == "oracle":
                for alias in node.names:
                    if alias.name in {"judge", "*"}:
                        return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] == "oracle":
                    return True
    return False


def _judge_calls(tree: ast.AST) -> int:
    return sum(1 for node in ast.walk(tree) if _call_attr(node) == "judge")


def _local_all_checklist(tree: ast.AST) -> bool:
    """Detect `return GO if all(local_list)` style completion AND."""
    assigned_lists: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        assigned_lists.add(tgt.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "all":
            if not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Name) and arg.id in assigned_lists:
                return True
            if isinstance(arg, (ast.List, ast.Tuple)):
                return True
    return False


def _exit_zero_as_go(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if isinstance(left, ast.Attribute) and left.attr == "exit_code":
            return True
        if isinstance(left, ast.Name) and left.id == "exit_code":
            return True
        if (
            isinstance(left, ast.Call)
            and isinstance(left.func, ast.Attribute)
            and left.func.attr == "get"
            and left.args
            and isinstance(left.args[0], ast.Constant)
            and left.args[0].value == "exit_code"
        ):
            return True
    return False


def analyze_source(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    imported = _imports_oracle_judge(tree)
    calls = _judge_calls(tree)
    local = _local_all_checklist(tree)
    exit_zero = _exit_zero_as_go(source)
    uses_shared = imported and calls >= 1 and not local and not exit_zero
    return {
        "imports_oracle_judge": imported,
        "judge_calls": calls,
        "local_checklist": local,
        "exit_zero_as_go": exit_zero,
        "uses_shared_oracle": uses_shared,
    }


def analyze_path(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    result = analyze_source(source)
    result["path"] = path.as_posix()
    return result


def rival_is_detected() -> dict[str, Any]:
    result = analyze_source(RIVAL_LOCAL_CHECKLIST)
    result["path"] = "planted-rival-local-checklist"
    return result
