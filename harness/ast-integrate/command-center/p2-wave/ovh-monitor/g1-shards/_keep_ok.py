#!/usr/bin/env python3
import json
from pathlib import Path

jl = Path(__file__).with_name("_shard11_measure.jsonl")
rows = {}
for ln in jl.read_text(encoding="utf-8").splitlines():
    if ln.strip():
        rec = json.loads(ln)
        rows[rec["id"]] = rec
ok = [r for r in rows.values() if r.get("ok")]
jl.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ok), encoding="utf-8")
print("kept", len(ok))
