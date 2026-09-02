#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

p = Path(__file__).with_name("_shard04_measure.jsonl")
ok = []
fail = []
for line in p.read_text(encoding="utf-8").splitlines():
    if not line.startswith("{"):
        continue
    rec = json.loads(line)
    if rec.get("ok"):
        ok.append(rec["id"])
    else:
        tail = rec.get("tail") or ""
        last = rec.get("last") or ""
        fail.append({"id": rec["id"], "last": last, "tail": tail[-900:]})
print(f"ok={len(ok)} {ok}")
print(f"fail={len(fail)}")
for f in fail:
    lines = [ln.strip() for ln in f["tail"].splitlines() if ln.strip()]
    interesting = [ln for ln in lines if "FAIL" in ln or "Error" in ln or "error" in ln or "MISSING" in ln or "drift" in ln]
    msg = interesting[-1] if interesting else (lines[-2] if len(lines) >= 2 else f["last"])
    print(f"{f['id']:10} {msg[:180]}")
