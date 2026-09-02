#!/usr/bin/env python3
"""List failing units whose tail mentions completion_predicate."""
import json
from pathlib import Path

P = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-local-full.jsonl")
latest = {}
for line in P.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        continue
    latest[rec.get("id")] = rec

for uid, rec in sorted(latest.items()):
    if rec.get("ok"):
        continue
    tail = str(rec.get("tail") or rec.get("out") or "")
    if "completion_predicate" in tail or "predicate" in tail.lower():
        print("==", uid)
        print(tail[-400:].replace("\\n", "\n"))
