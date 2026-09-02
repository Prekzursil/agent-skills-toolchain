#!/usr/bin/env python3
"""Merge shard-03 live + finish receipts into a per-id last-line table."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-03.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
live = json.loads((HERE / "_shard03_live.json").read_text(encoding="utf-8"))
fin = json.loads((HERE / "_shard03_finish.json").read_text(encoding="utf-8"))
by: dict[str, dict] = {}
for rec in live.get("rows") or []:
    by[rec["id"]] = rec
for rec in fin.get("rows") or []:
    by[rec["id"]] = rec  # finish is later for overlapping remesure ids

print("shard", len(IDS), "have_row", len(by), "missing", [i for i in IDS if i not in by])
ok = []
fail = []
for uid in IDS:
    rec = by.get(uid) or {}
    line = rec.get("line") or "NOT-MEASURED"
    is_ok = rec.get("ok") is True and str(line).startswith("SUCCESS:delivered ")
    (ok if is_ok else fail).append((uid, line, rec.get("rc")))
print("ok", len(ok), "fail", len(fail), "attempted", len(ok) + len(fail))
print("--- OK ---")
for uid, line, rc in ok:
    print(f"{uid}\t{line}")
print("--- FAIL ---")
for uid, line, rc in fail:
    print(f"{uid}\t{line}")
