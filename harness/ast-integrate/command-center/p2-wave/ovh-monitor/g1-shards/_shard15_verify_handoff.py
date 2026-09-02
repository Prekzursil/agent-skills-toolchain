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
raw = (HERE / "shard-15.remaining.txt").read_bytes().replace(b"\r\n", b"\n")
fp = hashlib.sha256(raw).hexdigest()
rows = [
    json.loads(ln)
    for ln in (HERE / "_shard15_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
by = {r["id"]: r for r in rows}
print("assigned", len(assigned), "unique", len(set(assigned)))
print("jsonl", len(rows), "unique", len(by))
print("remaining_file", len(remaining), "fp", fp)
print("missing_from_jsonl", [i for i in assigned if i not in by])
ok = []
fail = []
for uid in assigned:
    rec = by.get(uid) or {}
    last = rec.get("last") or ""
    is_ok = last == f"SUCCESS:delivered {uid}"
    (ok if is_ok else fail).append(uid)
print("ok_n", len(ok))
print("ok_ids", " ".join(ok))
print("fail_n", len(fail))
print("remaining_vs_fail_symdiff", sorted(set(remaining) ^ set(fail)))
print("---FAIL-TAILS---")
for uid in fail:
    rec = by[uid]
    lines = [ln.strip() for ln in (rec.get("tail") or "").splitlines() if ln.strip()]
    hint = rec.get("last") or ""
    for ln in reversed(lines):
        if ln.startswith("FAILED:") and f"delivered {uid}" not in ln:
            hint = ln
            break
        if "Error" in ln or "Error:" in ln or ln.startswith("  File "):
            hint = ln
            # keep looking for FAILED:
    print(f"{uid}\t{rec.get('last')}\t{hint[:220]}")
