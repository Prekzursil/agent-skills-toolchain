#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "_shard08_dump.json").read_text(encoding="utf-8"))
stdlib = {
    "os", "sys", "json", "re", "pathlib", "hashlib", "subprocess", "tempfile",
    "shutil", "typing", "collections", "itertools", "functools", "dataclasses",
    "copy", "io", "csv", "math", "time", "datetime", "argparse", "unittest",
    "traceback", "textwrap", "string", "struct", "base64", "binascii", "uuid",
    "glob", "fnmatch", "stat", "errno", "signal", "socket", "http", "urllib",
    "ssl", "hmac", "secrets", "logging", "contextlib", "abc", "enum", "types",
    "inspect", "importlib", "pkgutil", "ast", "tokenize", "keyword", "token",
    "difflib", "pprint", "platform", "posixpath", "ntpath", "genericpath",
    "configparser", "tomllib", "xml", "html", "email", "mimetypes", "gzip",
    "zipfile", "tarfile", "lzma", "bz2", "pickle", "decimal", "fractions",
    "random", "statistics", "operator", "weakref", "gc", "ctypes", "multiprocessing",
    "threading", "queue", "concurrent", "asyncio", "selectors", "select",
    "mmap", "array", "heapq", "bisect", "copyreg", "reprlib", "numbers",
    "__future__", "builtins", "warnings", "site", "runpy", "code", "codeop",
    "dis", "linecache", "py_compile", "compileall", "modulefinder", "pkgutil",
    "zipimport", "faulthandler", "tracemalloc", "gc", "sysconfig", "venv",
    "ensurepip", "pip", "setuptools", "distutils", "wheel",
}
skip_local = {"write_receipts", "emit_receipt", "audit", "isolate", "schema_local"}
froms = {}
for r in data["rows"]:
    for p in r.get("probes") or []:
        for f in p.get("froms") or []:
            if not f:
                continue
            root = f.split(".")[0]
            if root in stdlib:
                continue
            froms.setdefault(f, []).append(r["id"])
print("=== FROMS ===")
for f, ids in sorted(froms.items(), key=lambda kv: (-len(set(kv[1])), kv[0])):
    print(f"{f}\t{len(set(ids))}\t{','.join(sorted(set(ids))[:8])}")
print("\n=== ASSERT TAILS ===")
for r in data["rows"]:
    print(f"\n## {r['id']} {r['title'][:70]}")
    print("imports:", ", ".join(r.get("imports") or [])[:200])
    for a in (r.get("asserts") or [])[-8:]:
        print(" ", a[:180])
    for p in r.get("probes") or []:
        print(f"  -- {p['name']} froms={p.get('froms')}")
        for ln in (p.get("tail") or [])[-8:]:
            print("    ", ln[:160])
