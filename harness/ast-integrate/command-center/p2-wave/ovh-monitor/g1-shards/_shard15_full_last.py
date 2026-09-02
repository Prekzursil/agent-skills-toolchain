#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
assigned = [
    ln.strip()
    for ln in (HERE / "shard-15.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
remaining = [
    ln.strip()
    for ln in (HERE / "shard-15.remaining.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
rows = [
    json.loads(ln)
    for ln in (HERE / "_shard15_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
by = {r["id"]: r for r in rows}
fp = hashlib.sha256(
    (HERE / "shard-15.remaining.txt").read_bytes().replace(b"\r\n", b"\n")
).hexdigest()
print("ASSIGNED", len(assigned))
print("JSONL", len(rows), "ids", len(by))
print("REMAINING", len(remaining), "fp", fp)
print("---LAST-LINE-PER-ASSIGNED---")
ok = fail = 0
for uid in assigned:
    rec = by.get(uid)
    last = (rec or {}).get("last") or "MISSING"
    flag = "OK" if last == f"SUCCESS:delivered {uid}" else "FAIL"
    if flag == "OK":
        ok += 1
    else:
        fail += 1
    print(f"{flag}\t{uid}\trc={(rec or {}).get('rc')}\t{last}")
print("COUNTS ok", ok, "fail", fail)
print("---REMAINING-FILE---")
print("\n".join(remaining))
print("---SET-DIFF remaining-fail---")
fail_ids = [u for u in assigned if (by.get(u) or {}).get("last") != f"SUCCESS:delivered {u}"]
print("only_remaining", sorted(set(remaining) - set(fail_ids)))
print("only_fail", sorted(set(fail_ids) - set(remaining)))
