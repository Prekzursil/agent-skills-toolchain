#!/usr/bin/env python3
"""Re-run Windows probes for selected shard-19 IDs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _shard19_win_probes import run_one  # noqa: E402

IDS = sys.argv[1:] or [
    ln.strip()
    for ln in (HERE / "shard-19.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
OUT = HERE / "_shard19_rerun.jsonl"
if OUT.exists():
    OUT.unlink()
ok = fail = 0
with OUT.open("w", encoding="utf-8") as fh:
    for uid in IDS:
        rec = run_one(uid)
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        if rec.get("ok"):
            ok += 1
            print("OK", uid)
        else:
            fail += 1
            msg = (rec.get("fails") or ["?"])[0][:220]
            print("FAIL", uid, msg)
print(f"SUMMARY attempted={len(IDS)} ok={ok} fail={fail}")
