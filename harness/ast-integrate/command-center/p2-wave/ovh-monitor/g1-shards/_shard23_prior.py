#!/usr/bin/env python3
"""Pull last G-1 jsonl row for each shard-23 id."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-23.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
JSONL = HERE.parent / "g1-local-full.jsonl"
last: dict[str, dict] = {}
if JSONL.is_file():
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            uid = rec.get("id")
            if uid in IDS:
                last[uid] = rec
for uid in IDS:
    rec = last.get(uid) or {}
    ok = rec.get("ok")
    cls = rec.get("cls") or rec.get("reason") or ""
    line = str(rec.get("line") or rec.get("last") or "")[:180]
    tail = str(rec.get("tail") or "")
    tail_last = ""
    if tail:
        parts = [ln for ln in tail.splitlines() if ln.strip()]
        tail_last = (parts[-1] if parts else "")[:220]
    print(f"{uid} ok={ok} cls={cls} line={line}")
    if tail_last:
        print(f"  tail={tail_last}")
print(f"found={len(last)}/{len(IDS)}")
