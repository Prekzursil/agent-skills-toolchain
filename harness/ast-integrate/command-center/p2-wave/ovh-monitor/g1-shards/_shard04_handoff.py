#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
jsonl = HERE / "_shard04_measure.jsonl"
recs = []
for line in jsonl.read_text(encoding="utf-8").splitlines():
    if line.startswith("{"):
        recs.append(json.loads(line))
by = {r["id"]: r for r in recs}
print("jsonl_n", len(recs), "ids", len(IDS), "missing_from_jsonl", [u for u in IDS if u not in by])
ok, fail = [], []
for uid in IDS:
    rec = by.get(uid) or {}
    last = str(rec.get("last") or "")
    tail = str(rec.get("tail") or "")
    success = last.strip() == f"SUCCESS:delivered {uid}" or f"SUCCESS:delivered {uid}" in tail.splitlines()[-3:]
    if rec.get("ok") is True and success:
        ok.append(uid)
        print(f"OK  {uid} {last}")
    else:
        fail.append(uid)
        reason = last
        for ln in reversed(tail.splitlines()):
            s = ln.strip()
            if s.startswith("FAILED:") or "Error" in s or "Error:" in s:
                reason = s[:200]
                break
        print(f"FAIL {uid} {reason}")

rem = (HERE / "shard-04.remaining.txt").read_bytes().replace(b"\r\n", b"\n")
print("remaining_fp_live", hashlib.sha256(rem).hexdigest())
print("remaining_n_file", len([ln for ln in rem.decode().splitlines() if ln.strip()]))
print("ok", len(ok), "fail", len(fail))
