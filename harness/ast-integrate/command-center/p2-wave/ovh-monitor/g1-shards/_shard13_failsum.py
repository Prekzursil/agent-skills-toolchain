#!/usr/bin/env python3
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "_shard13_remeasure.jsonl"
for line in p.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r.get("ok"):
        print("OK", r["id"])
        continue
    tail = r.get("tail") or ""
    lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    interesting = [
        ln
        for ln in lines
        if ln.startswith("FAILED:") and "delivered" not in ln
    ]
    if not interesting:
        interesting = [
            ln
            for ln in lines
            if any(k in ln for k in ("Error:", "Error ", "ImportError", "ModuleNotFound", "AttributeError", "TypeError", "KeyError"))
        ]
    msg = interesting[-1] if interesting else (lines[-3] if len(lines) >= 3 else r.get("last"))
    print(f"{r['id']}: {msg[:200]}")
