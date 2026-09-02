#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-00.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]


def imports_of(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return [f"SYNTAX:{path.name}"]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = [a.name for a in node.names]
            out.append(f"from {mod} import {', '.join(names)}")
    return out


def main() -> None:
    rows = []
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        if not pdir.is_dir():
            print(uid, "NO PROBE DIR")
            continue
        rec = {"id": uid, "files": {}}
        for py in sorted(pdir.glob("*.py")):
            rec["files"][py.name] = imports_of(py)
        rows.append(rec)
        print("=" * 70)
        print(uid)
        for fn, imps in rec["files"].items():
            ext = [i for i in imps if not i.startswith(("from pathlib", "from typing", "json", "sys", "os", "hashlib", "datetime", "re", "subprocess", "tempfile", "shutil", "unittest", "from dataclasses", "from collections", "from copy", "io", "csv", "math", "time", "random", "textwrap", "itertools", "functools", "argparse", "traceback", "uuid", "base64", "hmac", "secrets", "socket", "threading", "http", "urllib", "xml", "html", "email", "logging", "platform", "stat", "fnmatch", "glob", "struct", "array", "enum", "abc", "contextlib", "weakref", "types", "inspect", "ast", "tokenize", "token", "keyword", "difflib", "pprint", "decimal", "fractions", "statistics", "string", "codecs", "locale", "gettext", "unicodedata", "from __future__"))]
            if ext:
                print(f"  {fn}:")
                for i in ext:
                    print(f"    {i}")
    (WAVE / "ovh-monitor" / "g1-shards" / "_shard00_imports.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
