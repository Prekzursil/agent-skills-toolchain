#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = [
    json.loads(ln)
    for ln in (HERE / "_shard15_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
lines_out = []
for r in sorted(rows, key=lambda x: x["id"]):
    if r.get("ok"):
        continue
    tail = r.get("tail") or ""
    last = [ln.rstrip() for ln in tail.splitlines() if ln.strip()][-12:]
    lines_out.append(f"===== {r['id']} {r.get('last')}")
    lines_out.extend(last)
    lines_out.append("")
text = "\n".join(lines_out) + "\n"
(HERE / "_shard15_last8.txt").write_text(text, encoding="utf-8")
print(text)
