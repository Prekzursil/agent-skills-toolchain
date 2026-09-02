#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]


def attrs(tree: ast.AST) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.setdefault(a.asname or a.name.split(".")[0], set())
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            for a in node.names:
                names.setdefault(root, set()).add(a.name)
                if a.asname:
                    names.setdefault(a.asname, set())
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.setdefault(node.value.id, set()).add(node.attr)
    return names


def main() -> None:
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        collected: dict[str, set[str]] = {}
        for p in sorted(pdir.glob("*.py")):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError:
                print(uid, p.name, "SYNTAX")
                continue
            for k, v in attrs(tree).items():
                collected.setdefault(k, set()).update(v)
        interesting = {
            k: sorted(v)
            for k, v in sorted(collected.items())
            if v and k not in {"json", "sys", "os", "Path", "subprocess", "tempfile", "unittest", "hashlib", "re", "ast", "copy", "inspect", "shutil", "datetime"}
        }
        print(uid, json_dumps := interesting)


if __name__ == "__main__":
    main()
