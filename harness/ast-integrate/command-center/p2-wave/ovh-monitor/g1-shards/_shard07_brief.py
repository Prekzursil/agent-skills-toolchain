#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "_shard07_dump.json"
rows = json.loads(p.read_text(encoding="utf-8"))
for r in rows:
    print("=" * 72)
    print(r["id"], r["title"][:90])
    print("out", r["output_path"], "bytes", r["output_bytes"])
    print("py", r["py_files"])
    print("cmds", r["named_cmds"][:4])
    print("imports", r["imports"])
    print("asserts:")
    for a in r["asserts"][:8]:
        print(" ", a[:160])
    heads = r.get("probe_heads") or {}
    tails = r.get("probe_tails") or {}
    for name, lines in heads.items():
        print(f"-- {name} head --")
        for ln in lines[:25]:
            print(" ", ln[:160])
    for name, lines in tails.items():
        if not lines:
            continue
        print(f"-- {name} tail --")
        for ln in lines[-12:]:
            print(" ", ln[:160])
