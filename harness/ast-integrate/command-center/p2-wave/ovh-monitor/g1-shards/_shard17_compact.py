#!/usr/bin/env python3
"""Compact shard-17 dump into API + assert briefs."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard17_dump.json").read_text(encoding="utf-8"))
SKIP = {
    "__future__",
    "os",
    "sys",
    "json",
    "pathlib",
    "re",
    "hashlib",
    "typing",
    "unittest",
    "pytest",
    "tempfile",
    "subprocess",
    "collections",
    "datetime",
    "functools",
    "itertools",
    "io",
    "copy",
    "math",
    "enum",
    "abc",
    "dataclasses",
    "argparse",
    "shutil",
    "textwrap",
    "inspect",
    "ast",
    "types",
    "contextlib",
    "warnings",
    "logging",
    "traceback",
    "glob",
    "fnmatch",
    "base64",
    "uuid",
    "time",
    "struct",
    "zlib",
    "gzip",
    "tarfile",
    "zipfile",
    "csv",
    "xml",
    "html",
    "http",
    "urllib",
    "ssl",
    "socket",
    "threading",
    "multiprocessing",
    "concurrent",
    "asyncio",
    "sqlite3",
    "decimal",
    "random",
    "string",
    "pprint",
    "hmac",
    "secrets",
    "platform",
    "importlib",
    "importlib.util",
    "shlex",
}

out = []
for r in rows:
    froms = []
    for src in r.get("imports") or []:
        root = src.split(".")[0]
        if root in SKIP or src in SKIP:
            continue
        froms.append(src)
    names = r.get("probe_names") or {}
    interesting = {}
    for pname, nmap in names.items():
        if not isinstance(nmap, dict):
            continue
        keep = {}
        for k, attrs in nmap.items():
            if k in SKIP or k in {"Path", "REPO", "HERE", "WAVE", "PROBES"}:
                continue
            if attrs:
                keep[k] = attrs[:20]
        if keep:
            interesting[pname] = keep
    miss = [
        k
        for k, v in (r.get("modules") or {}).items()
        if not v.get("hits") and k not in SKIP
    ]
    compact = {
        "id": r["id"],
        "title": (r.get("title") or "")[:140],
        "output_path": r.get("output_path"),
        "py_files": r.get("py_files"),
        "imports": froms,
        "miss": miss,
        "asserts": (r.get("asserts") or [])[:30],
        "named_cmds": r.get("named_cmds") or [],
        "sha_match": all(
            x.get("sha_match")
            for x in (r.get("manifest_rows") or []) or [{"sha_match": True}]
        ),
        "manifest_rows": r.get("manifest_rows"),
        "attrs": interesting,
        "heads": {k: v[:16] for k, v in (r.get("probe_heads") or {}).items()},
        "tails": {k: v[-18:] for k, v in (r.get("probe_tails") or {}).items()},
    }
    out.append(compact)

path = HERE / "_shard17_compact.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("n", len(out), "bytes", path.stat().st_size)
for c in out:
    print("---", c["id"], c["title"][:70])
    print("  miss", c["miss"][:8])
    print("  asserts", len(c["asserts"]))
    print("  sha", c["sha_match"], "cmds", len(c["named_cmds"]))
