#!/usr/bin/env python3
from pathlib import Path
import json

p = Path(__file__).resolve().parent / "_shard22_dump.json"
rows = json.loads(p.read_text(encoding="utf-8"))
for r in rows:
    miss = [m for m in (r.get("miss") or []) if m != "__future__"]
    a = r.get("asserts") or []
    print(f"{r['id']} miss={miss[:8]} asserts={len(a)} cmds={r['named_cmds']}")
    for s in a[:8]:
        print("   ", s[:180])
