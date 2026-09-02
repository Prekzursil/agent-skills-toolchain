#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
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
res = json.loads((here / "shard-19.txt.result.json").read_text(encoding="utf-8"))
by = {r["id"]: r for r in rows}
ok = [
    r["id"]
    for r in rows
    if r.get("ok") and r.get("last") == f"SUCCESS:delivered {r['id']}"
]
fail = [r["id"] for r in rows if r["id"] not in ok]
missing = [i for i in ids if i not in by]
extra = [r["id"] for r in rows if r["id"] not in ids]
print("assigned", len(ids), "jsonl", len(rows), "unique_jsonl", len(by))
print("missing", missing)
print("extra", extra)
print("ok", len(ok), "fail", len(fail))
print(
    "result attempted/ok/fail/verified",
    res.get("attempted"),
    res.get("ok"),
    res.get("fail"),
    res.get("verified"),
)
print("result_ok_ids_match", sorted(res.get("ok_ids") or []) == sorted(ok))
print("OK_IDS")
for i in sorted(ok):
    rec = by[i]
    print(f"  {i} rc={rec.get('rc')} last={rec.get('last')}")
print("FAIL_LAST")
for i in ids:
    if i not in ok:
        rec = by.get(i) or {}
        print(f"  {i} rc={rec.get('rc')} last={rec.get('last')}")
rem = here / "remaining_ids.txt"
raw = rem.read_bytes()
idsr = [ln.strip() for ln in rem.read_text(encoding="utf-8").splitlines() if ln.strip()]
print("remaining_n", len(idsr))
print("remaining_fp_raw", hashlib.sha256(raw).hexdigest())
print("remaining_fp_lf", hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest())
print("result remaining_fp", res.get("remaining_fp"))
print("result remaining_n", res.get("remaining_n"))
