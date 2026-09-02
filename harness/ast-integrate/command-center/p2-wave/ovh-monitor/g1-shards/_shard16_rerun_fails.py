#!/usr/bin/env python3
"""Re-run only previously failed shard-16 Windows probes."""
from __future__ import annotations

import json
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
JSONL = HERE / "_shard16_win_probes.jsonl"
spec = importlib.util.spec_from_file_location("win", HERE / "_shard16_win_probes.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failed = []
ok_keep = []
if JSONL.is_file():
    for ln in JSONL.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        if rec.get("ok"):
            ok_keep.append(rec)
        else:
            failed.append(rec["id"])

print("rerun", len(failed), "keep-ok", len(ok_keep))
rows = list(ok_keep)
for uid in failed:
    rec = mod.run_one(uid)
    rows.append(rec)
    mark = "OK" if rec.get("ok") else "FAIL"
    fail = (rec.get("fails") or ["?"])[0][:180]
    print(mark, uid, fail if mark == "FAIL" else "probes-pass")

# preserve original shard order
order = {uid: i for i, uid in enumerate(mod.IDS)}
rows.sort(key=lambda r: order.get(r["id"], 10**6))
JSONL.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
print("ok", sum(1 for r in rows if r.get("ok")), "fail", sum(1 for r in rows if not r.get("ok")))
