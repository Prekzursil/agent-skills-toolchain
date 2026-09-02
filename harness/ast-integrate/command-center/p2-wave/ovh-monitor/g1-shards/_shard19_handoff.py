#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

here = Path(__file__).resolve().parent
ids = [
    ln.strip()
    for ln in (here / "shard-19.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
rows = [
    json.loads(ln)
    for ln in (here / "_shard19_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
by = {r["id"]: r for r in rows}
fail_re = re.compile(r"(FAILED:[^\n]{0,220}|TIMEOUT|AttributeError:[^\n]{0,180}|TypeError:[^\n]{0,180}|ImportError:[^\n]{0,180}|KeyError:[^\n]{0,80}|RuntimeError:[^\n]{0,180})")
print("ASSIGNED", len(ids))
print("JSONL", len(rows))
for uid in ids:
    rec = by[uid]
    ok = rec.get("ok") and rec.get("last") == f"SUCCESS:delivered {uid}"
    tail = rec.get("tail") or ""
    hits = fail_re.findall(tail)
    marker = hits[-1] if hits else (rec.get("last") or "")[:220]
    print(f"{'OK' if ok else 'FAIL'}\t{uid}\trc={rec.get('rc')}\tlast={rec.get('last')}\tmarker={marker}")
