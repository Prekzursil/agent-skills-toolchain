#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
data = json.loads((HERE / "_shard08_dump.json").read_text(encoding="utf-8"))

paths = [
    str(REPO / "command-center" / "p2-wave" / "seed-stage"),
    str(REPO),
    str(REPO / "tools"),
    str(REPO / "tools" / "measure-guard"),
    str(REPO / "platform" / "lib"),
    str(REPO / "tools" / "agentspec"),
    str(REPO / "command-center"),
    str(REPO / "command-center" / "lib"),
]
for p in reversed(paths):
    if p not in sys.path:
        sys.path.insert(0, p)

skip_roots = {
    "__future__", "os", "sys", "json", "re", "pathlib", "hashlib", "subprocess",
    "tempfile", "shutil", "typing", "collections", "itertools", "functools",
    "dataclasses", "copy", "io", "csv", "math", "time", "datetime", "argparse",
    "unittest", "traceback", "textwrap", "string", "struct", "base64", "uuid",
    "glob", "fnmatch", "stat", "errno", "signal", "socket", "http", "urllib",
    "ssl", "hmac", "secrets", "logging", "contextlib", "abc", "enum", "types",
    "inspect", "importlib", "ast", "tokenize", "difflib", "pprint", "platform",
    "gzip", "zipfile", "tarfile", "pickle", "decimal", "random", "operator",
    "warnings", "runpy", "site", "html", "xml", "email", "mimetypes",
}

rows = []
seen = {}
for r in data["rows"]:
    pdir = REPO / "command-center" / "p2-wave" / "probes" / r["id"]
    extra = [str(pdir)] if pdir.is_dir() else []
    for p in reversed(extra):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    mods = sorted({f for p in r.get("probes") or [] for f in (p.get("froms") or []) if f})
    unit = {"id": r["id"], "mods": []}
    for mod in mods:
        root = mod.split(".")[0]
        if root in skip_roots:
            continue
        if mod.startswith("probe"):
            continue
        key = (r["id"], mod)
        try:
            importlib.import_module(mod)
            status = "ok"
            err = ""
        except Exception as exc:
            status = type(exc).__name__
            err = str(exc)[:240]
        unit["mods"].append({"mod": mod, "status": status, "err": err})
        seen.setdefault(mod, []).append((r["id"], status, err))
    rows.append(unit)
    for p in extra:
        if p in sys.path:
            sys.path.remove(p)

out = HERE / "_shard08_modcheck.json"
out.write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
print("=== MISSING/FAIL ===")
for mod, hits in sorted(seen.items()):
    bad = [h for h in hits if h[1] != "ok"]
    good = [h for h in hits if h[1] == "ok"]
    if bad:
        print(f"FAIL {mod}  bad={len(bad)} ok={len(good)}  {bad[0][1]}:{bad[0][2][:140]}  ids={','.join(h[0] for h in bad)}")
print("=== OK-ONLY (sample) ===")
for mod, hits in sorted(seen.items()):
    bad = [h for h in hits if h[1] != "ok"]
    if not bad:
        print(f"OK   {mod}  n={len(hits)}")
