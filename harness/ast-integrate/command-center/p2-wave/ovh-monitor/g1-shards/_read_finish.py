#!/usr/bin/env python3
import json
from pathlib import Path
p = Path(__file__).with_name("_shard03_finish.json")
print("exists", p.exists())
if not p.exists():
    raise SystemExit(0)
d = json.loads(p.read_text(encoding="utf-8"))
rows = d.get("rows") or []
print("n", len(rows), "ok", sum(1 for r in rows if r.get("ok")), "fail", sum(1 for r in rows if not r.get("ok")))
for r in rows:
    print(r["id"], "OK" if r.get("ok") else "FAIL", (r.get("line") or "")[:100])
