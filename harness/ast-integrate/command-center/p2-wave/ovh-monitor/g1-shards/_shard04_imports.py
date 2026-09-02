#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
STDLIB = {
    "abc", "argparse", "ast", "base64", "binascii", "builtins", "collections",
    "contextlib", "copy", "csv", "dataclasses", "datetime", "decimal", "difflib",
    "enum", "fnmatch", "functools", "glob", "gzip", "hashlib", "hmac", "html",
    "http", "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "logging", "math", "multiprocessing", "os", "pathlib", "pickle", "pkgutil",
    "platform", "plistlib", "pprint", "queue", "random", "re", "runpy", "shlex",
    "shutil", "signal", "socket", "sqlite3", "ssl", "stat", "string", "struct",
    "subprocess", "sys", "tempfile", "textwrap", "threading", "time", "tomllib",
    "traceback", "types", "typing", "unicodedata", "urllib", "uuid", "warnings",
    "xml", "zipfile", "zoneinfo", "__future__",
}

rows = []
for uid in IDS:
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    imports: dict[str, list[str]] = {}
    missing = []
    if pdir.is_dir():
        for py in sorted(pdir.glob("*.py")):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except Exception as exc:
                missing.append(f"parse:{py.name}:{exc}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        imports.setdefault(root, []).append(f"{py.name}:{alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    names = [a.name for a in node.names]
                    imports.setdefault(root, []).append(f"{py.name}:{node.module}:{','.join(names)}")
    unresolved = []
    for root in sorted(imports):
        if root in STDLIB:
            continue
        local = pdir / f"{root}.py"
        pkg = pdir / root / "__init__.py"
        repo_mod = REPO / f"{root}.py"
        repo_pkg = REPO / root / "__init__.py"
        tools_mod = REPO / "tools" / f"{root}.py"
        tools_pkg = REPO / "tools" / root / "__init__.py"
        plugin_mod = REPO / "tools" / "plugin" / f"{root}.py"
        platform_pkg = REPO / "platform" / "lib" / f"{root}.py"
        if any(p.is_file() for p in (local, pkg, repo_mod, repo_pkg, tools_mod, tools_pkg, plugin_mod, platform_pkg)):
            continue
        unresolved.append({"mod": root, "uses": imports[root][:6]})
    rows.append({"id": uid, "unresolved": unresolved, "imports": {k: v[:4] for k, v in imports.items() if k not in STDLIB}})

(HERE / "_shard04_imports.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
for r in rows:
    if r["unresolved"]:
        print(f"{r['id']:10} MISSING {r['unresolved']}")
    else:
        print(f"{r['id']:10} imports-ok {list(r['imports'])}")
