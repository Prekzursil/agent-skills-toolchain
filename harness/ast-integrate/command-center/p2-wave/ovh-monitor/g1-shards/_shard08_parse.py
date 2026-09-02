#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = []
for ln in (HERE / "_shard08_measure.jsonl").read_text(encoding="utf-8").splitlines():
    if ln.strip():
        rows.append(json.loads(ln))
print("n", len(rows))
ok = [r for r in rows if r.get("status") == "ok"]
fail = [r for r in rows if r.get("status") != "ok"]
print("ok", len(ok), [r["id"] for r in ok])
print("fail", len(fail))
for r in fail:
    last = r.get("last") or ""
    tail = " | ".join((r.get("tail") or [])[-3:])[:220]
    print(f"{r['id']}\t{last[:80]}\t{tail}")
