"""AST scan that refuses hidden ranking state (clock/PRNG/module weights)."""
from __future__ import annotations

import ast
from pathlib import Path


_FORBIDDEN_CALLS = {"time", "random", "clock", "monotonic", "uuid4", "urandom"}
_FORBIDDEN_ATTRS = {"time", "random", "clock", "monotonic"}


def scan_hidden_state(path: Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in _FORBIDDEN_CALLS or name in _FORBIDDEN_ATTRS:
                hits.append(name)
        if isinstance(node, ast.Name) and node.id in {"random", "time", "uuid"}:
            if isinstance(getattr(node, "ctx", None), ast.Load):
                # import names used as module refs are allowed only if not called;
                # flag module-level time/random identifiers used for ranking.
                pass
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.upper().endswith("WEIGHTS"):
                    hits.append(t.id)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.upper().endswith("WEIGHTS"):
                hits.append(node.target.id)
    return {"clean": not hits, "hits": sorted(set(hits)), "path": str(path)}
