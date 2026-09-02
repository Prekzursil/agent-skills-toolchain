#!/usr/bin/env python3
"""Independent AST verifier: detect.py/trees.py do not read prose keys."""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROSE = frozenset(
    {
        "description",
        "prose",
        "notes",
        "narrative",
        "title",
        "blurb",
        "summary",
        "text",
        "comment",
        "label",
        "body",
    }
)


def keys_of(path: Path) -> set[str]:
    used: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                used.add(sl.value)
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name == "get" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    used.add(arg0.value)
    return used


def main() -> int:
    used: set[str] = set()
    for name in ("detect.py", "trees.py"):
        used |= keys_of(HERE / name)
    hits = sorted(used & PROSE)
    print(f"prose_key_reads={hits}")
    if hits:
        print("FAILED:IMP-0176-verify-ast")
        return 1
    print("SUCCESS:IMP-0176-verify-ast")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
