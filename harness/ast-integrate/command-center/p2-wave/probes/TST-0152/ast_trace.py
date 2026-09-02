"""Static proof: classify_agent never uses mtime in a control-flow test."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def _mentions_mtime(node: ast.AST) -> list[str]:
    hits: list[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and "mtime" in n.id.lower():
            hits.append(n.id)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and "mtime" in n.value.lower():
            if n.value in {"file_mtime"} or "artifact_mtime" in n.value:
                hits.append(repr(n.value))
    return hits


def scan_classify_agent(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "classify_agent":
            fn = node
            break
    if fn is None:
        return {"ok": False, "error": "classify_agent-missing"}

    mtime_in_tests: list[str] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.If):
            mtime_in_tests.extend(_mentions_mtime(node.test))
        elif isinstance(node, ast.While):
            mtime_in_tests.extend(_mentions_mtime(node.test))
        elif isinstance(node, ast.Assert):
            mtime_in_tests.extend(_mentions_mtime(node.test))
        elif isinstance(node, ast.Compare):
            mtime_in_tests.extend(_mentions_mtime(node))
        elif isinstance(node, ast.IfExp):
            mtime_in_tests.extend(_mentions_mtime(node.test))

    observational_copy = "observational_mtime_age_s" in source and "artifact_mtime_age_s" in source
    return {
        "ok": len(mtime_in_tests) == 0,
        "function": "classify_agent",
        "mtime_in_control_flow": mtime_in_tests,
        "observational_copy_present": observational_copy,
    }


def scan_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    result = scan_classify_agent(text)
    result["path"] = path.as_posix()
    result["bytes"] = len(text.encode("utf-8"))
    return result
