#!/usr/bin/env python3
from pathlib import Path
import json

p = Path(__file__).with_name("_shard22_measure.jsonl")
last = {}
for ln in p.read_text(encoding="utf-8").splitlines():
    if ln.strip():
        rec = json.loads(ln)
        last[rec["id"]] = rec
ok_lines = [json.dumps(rec, ensure_ascii=False) for rec in last.values() if rec.get("ok")]
p.write_text("\n".join(ok_lines) + ("\n" if ok_lines else ""), encoding="utf-8")
print("kept", len(ok_lines))
print(" ".join(sorted(r["id"] for r in last.values() if r.get("ok"))))
