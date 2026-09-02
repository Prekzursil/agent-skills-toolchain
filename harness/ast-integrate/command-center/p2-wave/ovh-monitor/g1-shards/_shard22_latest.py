#!/usr/bin/env python3
from pathlib import Path
import json

p = Path(__file__).with_name("_shard22_measure.jsonl")
last = {}
for ln in p.read_text(encoding="utf-8").splitlines():
    if ln.strip():
        rec = json.loads(ln)
        last[rec["id"]] = rec
ok = [r for r in last.values() if r.get("ok")]
fail = [r for r in last.values() if not r.get("ok")]
print(f"n={len(last)} ok={len(ok)} fail={len(fail)}")
print("OK", " ".join(sorted(r["id"] for r in ok)))
print("FAIL", " ".join(sorted(r["id"] for r in fail)))
for r in sorted(fail, key=lambda x: x["id"]):
    tail = r.get("tail") or ""
    lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    interesting = [ln for ln in lines if "FAILED:" in ln or "Error" in ln or "Error:" in ln or ln.startswith("  ")]
    msg = (interesting[-1] if interesting else (lines[-2] if len(lines) > 1 else r.get("line")))[:220]
    print(f"  {r['id']}: {msg}")
