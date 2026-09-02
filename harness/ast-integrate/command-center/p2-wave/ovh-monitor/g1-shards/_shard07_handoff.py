#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

G = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (G / "shard-07.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
rows: dict[str, dict] = {}
for name in ("_shard07_g1_measure.jsonl", "_shard07_g1_remeasure.jsonl"):
    p = G / name
    print("FILE", name, "exists", p.is_file(), "bytes", p.stat().st_size if p.is_file() else 0)
    if not p.is_file():
        continue
    n = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        n += 1
        rows[rec["id"]] = rec
    print(" rows", n)
print("MERGED", len(rows), "ok", sum(1 for r in rows.values() if r.get("ok")), "fail", sum(1 for r in rows.values() if not r.get("ok")))
missing = [u for u in IDS if u not in rows]
print("UNMEASURED", missing)
for uid in IDS:
    rec = rows.get(uid) or {}
    last = str(rec.get("last") or "NO-MEASURE")
    flag = "OK" if rec.get("ok") else "FAIL"
    print(f"{uid}\t{flag}\t{last[:220]}")
