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
result = json.loads((HERE / "shard-15.txt.result.json").read_text(encoding="utf-8"))
rows = [
    json.loads(ln)
    for ln in (HERE / "_shard15_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
by = {r["id"]: r for r in rows}
fp = hashlib.sha256(
    (HERE / "shard-15.remaining.txt").read_bytes().replace(b"\r\n", b"\n")
).hexdigest()
out = []
for uid in assigned:
    rec = by.get(uid)
    last = (rec or {}).get("last") or "MISSING-JSONL"
    ok = last == f"SUCCESS:delivered {uid}"
    lines = [ln.strip() for ln in ((rec or {}).get("tail") or "").splitlines() if ln.strip()]
    probe_fail = ""
    for ln in reversed(lines):
        if ln.startswith("FAILED:") and f"delivered {uid}" not in ln:
            probe_fail = ln
            break
    if not probe_fail:
        for ln in reversed(lines):
            if any(k in ln for k in ("Error", "Error:", "AttributeError", "ImportError", "KeyError", "TIMEOUT", "RuntimeError")):
                probe_fail = ln
                break
    out.append(
        {
            "id": uid,
            "ok": ok,
            "rc": (rec or {}).get("rc"),
            "last": last,
            "probe_fail": probe_fail[:240],
        }
    )
payload = {
    "assigned_n": len(assigned),
    "jsonl_n": len(rows),
    "ok": [r["id"] for r in out if r["ok"]],
    "fail": [r for r in out if not r["ok"]],
    "remaining_n": len(remaining),
    "remaining_fp_live": fp,
    "remaining_fp_result": result.get("remaining_fp"),
    "fp_match": fp == result.get("remaining_fp"),
    "remaining_equals_fail": remaining == [r["id"] for r in out if not r["ok"]],
}
print(json.dumps(payload, indent=2))
