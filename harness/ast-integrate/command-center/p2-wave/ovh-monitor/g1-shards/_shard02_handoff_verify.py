#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards")

shard = [ln.strip() for ln in (HERE / "shard-02.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
remaining = [ln.strip() for ln in (HERE / "shard-02.remaining.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
raw = (HERE / "shard-02.remaining.txt").read_bytes()
fp = hashlib.sha256(raw).hexdigest()
result = json.loads((HERE / "shard-02.txt.result.json").read_text(encoding="utf-8"))

wave1 = {}
for ln in (HERE / "_shard02_measure.jsonl").read_text(encoding="utf-8").splitlines():
    if ln.strip():
        row = json.loads(ln)
        wave1[row["id"]] = row
wave2 = {}
p2 = HERE / "_shard02_fail_remeasure.jsonl"
if p2.is_file():
    for ln in p2.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            row = json.loads(ln)
            wave2[row["id"]] = row

latest = dict(wave1)
latest.update(wave2)
ok = [uid for uid in shard if latest.get(uid, {}).get("status") == "ok"]
fail = [uid for uid in shard if latest.get(uid, {}).get("status") != "ok"]
missing_measure = [uid for uid in shard if uid not in latest]

print("shard_n", len(shard))
print("measured", len(latest), "missing_measure", missing_measure)
print("latest_ok", len(ok), ok)
print("latest_fail", len(fail), len(fail))
print("remaining_n", len(remaining), "remaining==fail", remaining == fail)
print("remaining_fp_live", fp)
print("remaining_fp_result", result.get("remaining_fp"))
print("fp_match", fp == result.get("remaining_fp"))
print("bytes remaining", len(raw), "crlf", b"\r\n" in raw)
