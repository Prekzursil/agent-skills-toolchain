#!/usr/bin/env python3
"""Find imported modules for shard-04 probes and whether they are g1 stubs."""
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
STUB_MARKERS = ("# g1-surface: generated", "# g1-mod: real-surface", "class _NS:")

rows = []
for uid in IDS:
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    if not pdir.is_dir():
        continue
    imports: dict[str, list[str]] = {}
    for py in pdir.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [a.name for a in node.names]
                imports.setdefault(node.module, []).extend(names)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    imports.setdefault(a.name, [])
    stub_hits = []
    for mod, names in sorted(imports.items()):
        if mod in {
            "json", "sys", "os", "pathlib", "hashlib", "re", "copy", "tempfile",
            "subprocess", "shutil", "ast", "typing", "dataclasses", "enum",
            "datetime", "collections", "itertools", "functools", "traceback",
            "argparse", "textwrap", "io", "inspect", "stat", "errno", "signal",
            "time", "math", "random", "string", "uuid", "base64", "hmac",
            "struct", "fnmatch", "glob", "csv", "gzip", "zipfile", "tarfile",
            "urllib", "http", "ssl", "socket", "threading", "multiprocessing",
            "unittest", "pytest", "jsonschema", "yaml", "tomllib",
        } or mod.startswith(("probe", "emit", "write", "scenario", "engine", "fixtures", "contract", "schema")):
            continue
        # resolve under tools/ and repo
        parts = mod.split(".")
        candidates = [
            REPO / "tools" / Path(*parts).with_suffix(".py"),
            REPO / "tools" / Path(*parts) / "__init__.py",
            REPO / Path(*parts).with_suffix(".py"),
            REPO / Path(*parts) / "__init__.py",
        ]
        found = next((c for c in candidates if c.is_file()), None)
        kind = "missing"
        head = ""
        if found:
            head = found.read_text(encoding="utf-8", errors="replace")[:400]
            if any(m in head for m in STUB_MARKERS) or "return _call(" in head:
                kind = "stub"
            else:
                kind = "real"
        stub_hits.append(
            {
                "mod": mod,
                "names": sorted(set(names)),
                "kind": kind,
                "path": str(found.relative_to(REPO)).replace("\\", "/") if found else None,
            }
        )
    rows.append({"id": uid, "mods": stub_hits})

out = HERE / "_shard04_stubscan.json"
out.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
print(f"wrote {out}")
for r in rows:
    stubs = [m for m in r["mods"] if m["kind"] in {"stub", "missing"}]
    if not stubs:
        continue
    print(f"{r['id']}")
    for m in stubs:
        print(f"  {m['kind']:7} {m['mod']} {m['names'][:8]} {m['path']}")
