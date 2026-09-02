#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
assigned = [
    ln.strip()
    for ln in (HERE / "shard-22.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
last: dict[str, dict] = {}
for ln in (HERE / "_shard22_measure.jsonl").read_text(encoding="utf-8").splitlines():
    if not ln.strip():
        continue
    rec = json.loads(ln)
    if rec.get("id"):
        last[rec["id"]] = rec
remain_text = (HERE / "shard-22.remaining.txt").read_text(encoding="utf-8")
remain_ids = [ln.strip() for ln in remain_text.splitlines() if ln.strip()]
fp = hashlib.sha256(remain_text.encode("utf-8")).hexdigest()
raw = (HERE / "shard-22.remaining.txt").read_bytes()
fp2 = hashlib.sha256(raw).hexdigest()

print("ASSIGNED", len(assigned))
print("JSONL_LAST", len(last))
print("UNMEASURED", [u for u in assigned if u not in last])
ok = [u for u in assigned if last.get(u, {}).get("ok")]
fail = [u for u in assigned if not last.get(u, {}).get("ok")]
print("OK_N", len(ok))
print("FAIL_N", len(fail))
print("OK", " ".join(ok))
print("REMAIN_FILE_N", len(remain_ids))
print("REMAIN_FP_TEXT", fp)
print("REMAIN_FP_BYTES", fp2)
print("REMAIN_EQ_FAIL", remain_ids == fail)
print("---FAIL_TAILS---")
for uid in fail:
    rec = last[uid]
    tail = rec.get("tail") or ""
    hits = [
        ln.strip()
        for ln in tail.splitlines()
        if (
            ("FAILED:" in ln and "FAILED:delivered" not in ln)
            or "Error" in ln
            or "ModuleNotFoundError" in ln
            or "ImportError" in ln
            or "AttributeError" in ln
            or "KeyError" in ln
            or "TypeError" in ln
            or "AssertionError" in ln
        )
    ]
    msg = hits[-1] if hits else (rec.get("line") or "")[:240]
    print(f"{uid}|{rec.get('cls')}|{msg[:240]}")
