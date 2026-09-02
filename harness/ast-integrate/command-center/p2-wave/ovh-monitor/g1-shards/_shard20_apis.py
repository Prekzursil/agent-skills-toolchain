#!/usr/bin/env python3
"""Compact API + assertion harvest for shard-20 failing probes."""
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
JSONL = HERE / "_shard20_win_probes.jsonl"

STDLIB = {
    "os", "sys", "json", "pathlib", "re", "hashlib", "typing", "unittest",
    "tempfile", "subprocess", "collections", "datetime", "functools",
    "itertools", "io", "copy", "math", "enum", "abc", "dataclasses",
    "argparse", "shutil", "textwrap", "inspect", "ast", "types",
    "contextlib", "warnings", "logging", "traceback", "glob", "fnmatch",
    "base64", "uuid", "time", "struct", "zlib", "gzip", "tarfile",
    "zipfile", "csv", "xml", "html", "http", "urllib", "ssl", "socket",
    "threading", "multiprocessing", "concurrent", "asyncio", "sqlite3",
    "decimal", "random", "string", "pprint", "hmac", "secrets", "platform",
    "stat", "errno", "signal", "ctypes", "__future__", "importlib",
}


def attrs(text: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"error": str(exc)}
    froms: dict[str, list[str]] = {}
    uses: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            froms.setdefault(node.module, [])
            for a in node.names:
                froms[node.module].append(a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                froms.setdefault(a.name, [])
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            uses.setdefault(node.value.id, []).append(node.attr)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            uses.setdefault(node.func.id, []).append("__call__")
    for d in (froms, uses):
        for k, v in list(d.items()):
            d[k] = sorted(set(v))
    return {"froms": froms, "uses": uses}


def main() -> None:
    fails = {}
    if JSONL.is_file():
        for line in JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            fails[rec["id"]] = rec
    out = []
    for uid, rec in fails.items():
        if rec.get("ok"):
            continue
        pdir = PROBES / uid
        probes = []
        for p in sorted(pdir.glob("probe*.py")):
            if p.name in {"probe1.py", "probe2.py"}:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            info = attrs(text)
            froms = {
                k: v
                for k, v in (info.get("froms") or {}).items()
                if k.split(".")[0] not in STDLIB
            }
            uses = {
                k: v
                for k, v in (info.get("uses") or {}).items()
                if k.split(".")[0] not in STDLIB
                and k not in {"print", "len", "str", "int", "list", "dict", "set", "tuple", "bool", "bytes", "Path", "open"}
            }
            probes.append(
                {
                    "name": p.name,
                    "froms": froms,
                    "uses": uses,
                    "head": text.splitlines()[:50],
                    "asserts": [
                        ln.strip()
                        for ln in text.splitlines()
                        if ln.strip().startswith("assert ") or "FAILED:" in ln
                    ][:30],
                }
            )
        helpers = []
        for p in sorted(pdir.glob("*.py")):
            if p.name.startswith("probe"):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            info = attrs(text)
            froms = {
                k: v
                for k, v in (info.get("froms") or {}).items()
                if k.split(".")[0] not in STDLIB
            }
            if froms:
                helpers.append({"name": p.name, "froms": froms})
        out.append(
            {
                "id": uid,
                "fail": (rec.get("fails") or [""])[0][:240],
                "probes": probes,
                "helpers": helpers,
            }
        )
    dest = HERE / "_shard20_apis.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("n_fail", len(out), "wrote", dest)
    for r in out:
        mods = []
        for p in r["probes"]:
            mods.extend(p.get("froms") or {})
        for h in r["helpers"]:
            mods.extend(h.get("froms") or {})
        print(f"{r['id']}\t{r['fail'][:90]}\tmods={sorted(set(mods))[:8]}")


if __name__ == "__main__":
    main()
