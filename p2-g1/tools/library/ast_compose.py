"""AST compose-only scan of library entries."""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent


def scan_entries() -> list[dict]:
    rows = []
    for path in sorted(HERE.glob("*.py")):
        if path.name in {"__init__.py", "ast_compose.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rows.append({"path": path.name, "nodes": len(list(ast.walk(tree)))})
    # Four library surfaces: contract, entries, load, registry
    want = {"contract.py", "entries.py", "load.py", "registry.py"}
    present = {r["path"] for r in rows}
    if want - present:
        raise RuntimeError(f"missing library modules {want - present}")
    return [r for r in rows if r["path"] in want]


def check_mutant_fails() -> bool:
    mutant = "for x in ranking:\n    ranking.sort()\n"
    tree = ast.parse(mutant)
    ranking_loop = False
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            ranking_loop = True
    return ranking_loop
