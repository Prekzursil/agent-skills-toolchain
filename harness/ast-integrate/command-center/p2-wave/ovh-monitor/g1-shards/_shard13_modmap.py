#!/usr/bin/env python3
"""List imported production modules vs stub/missing for shard-13."""
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-13.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
STUB = ("# g1-surface: generated", "# g1-mod: real-surface", "class _NS:")
STD = {
    "os", "sys", "json", "pathlib", "re", "hashlib", "typing", "unittest",
    "tempfile", "subprocess", "collections", "datetime", "functools",
    "itertools", "io", "copy", "math", "enum", "abc", "dataclasses",
    "argparse", "shutil", "textwrap", "inspect", "ast", "types",
    "contextlib", "warnings", "logging", "traceback", "glob", "fnmatch",
    "base64", "uuid", "time", "struct", "zlib", "gzip", "tarfile",
    "zipfile", "csv", "xml", "html", "http", "urllib", "ssl", "socket",
    "threading", "multiprocessing", "concurrent", "asyncio", "sqlite3",
    "decimal", "statistics", "random", "string", "pprint", "difflib",
    "hmac", "secrets", "platform", "stat", "errno", "signal", "ctypes",
    "__future__", "jsonschema",
}


def imports_of(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
    return out


def locate(mod: str) -> dict:
    parts = mod.split(".")
    cands = [
        REPO.joinpath(*parts).with_suffix(".py"),
        REPO.joinpath(*parts) / "__init__.py",
        (REPO / "tools").joinpath(*parts).with_suffix(".py"),
        (REPO / "tools").joinpath(*parts) / "__init__.py",
        (REPO / "tools" / "agentspec").joinpath(*parts).with_suffix(".py"),
        (REPO / "tools" / "agentspec").joinpath(*parts) / "__init__.py",
        (REPO / "platform" / "lib").joinpath(*parts).with_suffix(".py"),
        (REPO / "command-center").joinpath(*parts).with_suffix(".py"),
        (REPO / "command-center").joinpath(*parts) / "__init__.py",
    ]
    hits = []
    for p in cands:
        if p.is_file():
            head = p.read_text(encoding="utf-8", errors="replace")[:1200]
            stub = any(m in head for m in STUB)
            hits.append(
                {
                    "path": str(p.relative_to(REPO)).replace("\\", "/"),
                    "bytes": p.stat().st_size,
                    "stub": stub,
                }
            )
    return {"hits": hits}


def main() -> None:
    rows = []
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        mods = []
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            for m in imports_of(text):
                root = m.split(".")[0]
                if root in STD:
                    continue
                # local probe-dir modules are fine
                local_py = pdir / f"{m.split('.')[0]}.py"
                local_pkg = pdir / m.split(".")[0] / "__init__.py"
                if local_py.is_file() or local_pkg.is_file():
                    continue
                info = locate(m)
                mods.append({"import": m, "probe": p.name, **info})
        rows.append({"id": uid, "mods": mods})
    dest = HERE / "_shard13_modmap.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", dest)
    for r in rows:
        if not r["mods"]:
            print(f"{r['id']} local-only")
            continue
        bits = []
        for m in r["mods"]:
            if not m["hits"]:
                bits.append(f"MISS:{m['import']}")
            elif any(h["stub"] for h in m["hits"]):
                bits.append(f"STUB:{m['import']}->{m['hits'][0]['path']}")
            else:
                bits.append(f"OK:{m['import']}->{m['hits'][0]['path']}({m['hits'][0]['bytes']})")
        print(f"{r['id']} " + " ; ".join(bits))


if __name__ == "__main__":
    main()
