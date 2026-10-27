#!/usr/bin/env python3
"""List failing unit IDs whose tail matches a substring, plus one sample tail.

Usage: python3 _g1_cluster_members.py "<substring>" [n_tail_chars]
Reads latest-state from g1-local-full.jsonl, then overlays every
repair-claude/*.jsonl so already-repaired units are excluded.
"""
import json
import sys
from pathlib import Path

MON = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor")
needle = sys.argv[1]
ntail = int(sys.argv[2]) if len(sys.argv) > 2 else 900

latest = {}
for src in [MON / "g1-local-full.jsonl", MON / "g1-fails-rerun.jsonl", *sorted((MON / "repair-claude").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)]:
    if not src.is_file():
        continue
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[rec.get("id")] = rec

members = []
for uid, rec in sorted(latest.items()):
    if rec.get("ok"):
        continue
    tail = str(rec.get("tail") or rec.get("out") or "")
    if needle in tail:
        members.append((uid, tail))

print("members", len(members))
print(" ".join(u for u, _ in members))
if members:
    uid, tail = members[0]
    print("== sample", uid)
    print(tail[-ntail:])
