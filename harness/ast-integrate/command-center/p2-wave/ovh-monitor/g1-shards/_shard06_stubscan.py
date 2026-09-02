#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
rows = json.loads((HERE / "_shard06_modcheck.json").read_text(encoding="utf-8"))
markers = ("g1-surface", "g1-mod:", "class _NS", "return Result()", "return _call(")
for rec in rows:
    for m in rec["mods"]:
        p = m.get("path")
        if not p:
            print("NOFILE", rec["id"], m["mod"])
            continue
        path = REPO / p
        if not path.is_file():
            print("MISSINGFILE", rec["id"], p)
            continue
        t = path.read_text(encoding="utf-8", errors="replace")
        hits = [mk for mk in markers if mk in t]
        if hits:
            print(f"STUB {rec['id']:10} {p} bytes={path.stat().st_size} {hits}")
