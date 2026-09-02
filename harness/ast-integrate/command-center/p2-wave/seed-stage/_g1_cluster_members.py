#!/usr/bin/env python3
"""List failing unit IDs whose tail matches a substring, plus one sample tail.

Usage: python3 _g1_cluster_members.py "<substring>" [n_tail_chars]
Reads latest-state from g1-local-full.jsonl, then overlays every
repair-claude/*.jsonl so already-repaired units are excluded.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import latest_rows  # noqa: E402  (02.09: Linux-native path fallback)

needle = sys.argv[1]
ntail = int(sys.argv[2]) if len(sys.argv) > 2 else 900

latest = latest_rows()

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
