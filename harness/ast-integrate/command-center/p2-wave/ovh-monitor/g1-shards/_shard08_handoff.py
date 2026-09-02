#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = [
    json.loads(l)
    for l in (HERE / "_shard08_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if l.strip()
]
print("JSONL_BYTES", (HERE / "_shard08_measure.jsonl").stat().st_size)
print("N", len(rows))
ok = fail = 0
for r in rows:
    last = str(r.get("last") or "")
    tail = [t for t in (r.get("tail") or []) if str(t).strip()]
    snippet = " | ".join(tail[-5:])[:280]
    if last.startswith("SUCCESS:delivered"):
        ok += 1
        mark = "OK"
    else:
        fail += 1
        mark = "FAIL"
    print(f"{mark}\t{r.get('id')}\t{last}\t{snippet}")
print("TOTAL_OK", ok, "TOTAL_FAIL", fail)
