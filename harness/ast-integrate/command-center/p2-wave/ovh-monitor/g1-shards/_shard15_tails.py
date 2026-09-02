#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = [
    json.loads(ln)
    for ln in (HERE / "_shard15_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
out = []
for r in rows:
    tail = r.get("tail") or ""
    lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    fail_lines = [ln for ln in lines if "FAIL" in ln or "Error" in ln or "error" in ln or "Assertion" in ln]
    out.append(
        {
            "id": r["id"],
            "ok": r["ok"],
            "last": r.get("last"),
            "fail_lines": fail_lines[-12:],
            "last8": lines[-8:],
        }
    )
dest = HERE / "_shard15_tails.json"
dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
ok = sum(1 for r in out if r["ok"])
print(f"n={len(out)} ok={ok} fail={len(out)-ok}")
for r in out:
    if r["ok"]:
        print("OK", r["id"])
        continue
    hint = r["fail_lines"][-1] if r["fail_lines"] else (r["last8"][-1] if r["last8"] else r["last"])
    print(r["id"], "|", hint[:200])
