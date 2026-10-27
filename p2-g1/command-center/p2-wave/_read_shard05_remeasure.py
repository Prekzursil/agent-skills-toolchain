#!/usr/bin/env python3
import json
from pathlib import Path

p = Path.home() / "p2-g1" / "_g1_shard05_remeasure.jsonl"
print("path", p, "exists", p.is_file(), "bytes", p.stat().st_size if p.is_file() else 0)
ok = fail = 0
for ln in p.read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    if rec.get("ok"):
        ok += 1
        continue
    fail += 1
    print("====", rec["id"], rec.get("line"))
    for t in (rec.get("tail") or "").splitlines():
        if any(k in t for k in ("FAILED", "Error", "assert", "ModuleNotFound", "probe[", "Traceback", "Unresolvable", "KeyError", "AttributeError", "ImportError", "TypeError")):
            print(t[:400])
print("ok", ok, "fail", fail)
