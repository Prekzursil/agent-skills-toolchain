#!/usr/bin/env python3
"""Print latest ok-status for the given unit IDs from g1-local-full.jsonl."""
import json
import sys
from pathlib import Path

P = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-local-full.jsonl")
ids = sys.argv[1:]
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
for uid in ids:
    rec = latest.get(uid)
    if rec is None:
        print(uid, "MISSING")
    else:
        print(uid, "OK" if rec.get("ok") else "FAIL")
