#!/usr/bin/env python3
"""Rebuild shard-03 coverage table from persisted JSON receipts only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (HERE / "shard-03.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
live = json.loads((HERE / "_shard03_live.json").read_text(encoding="utf-8"))
fin = json.loads((HERE / "_shard03_finish.json").read_text(encoding="utf-8"))
rem = HERE / "remaining_ids.txt"
raw = rem.read_bytes()


def probe_fail(tail: str) -> str:
    hits = []
    for ln in (tail or "").splitlines():
        s = ln.strip()
        if s.startswith("FAILED:") and "delivered" not in s:
            hits.append(s[:200])
        for tok in (
            "ModuleNotFoundError",
            "AttributeError",
            "TypeError",
            "KeyError",
            "FileNotFoundError",
            "ImportError",
        ):
            if s.startswith(tok) or f"{tok}:" in s[:40]:
                hits.append(s[:200])
    return hits[-1] if hits else ""


by = {r["id"]: dict(r, src="live") for r in live.get("rows") or []}
for r in fin.get("rows") or []:
    by[r["id"]] = dict(r, src="finish")

print("ids", len(IDS))
print("rows", len(by))
print("missing", [i for i in IDS if i not in by])
print("remaining_n", len([ln for ln in raw.decode("utf-8").splitlines() if ln.strip()]))
print("remaining_fp", hashlib.sha256(raw).hexdigest())
print("remaining_bytes", len(raw))

ok = fail = 0
print("---TABLE---")
for uid in IDS:
    rec = by.get(uid) or {}
    line = rec.get("line") or "NOT-MEASURED"
    is_ok = rec.get("ok") is True and str(line).startswith("SUCCESS:delivered ")
    reason = "" if is_ok else (probe_fail(rec.get("tail") or "") or line)
    src = rec.get("src") or "none"
    if is_ok:
        ok += 1
        print(f"OK\t{uid}\t{src}\t{line}")
    else:
        fail += 1
        print(f"FAIL\t{uid}\t{src}\t{reason}")
print(f"SUM attempted={len(IDS)} ok={ok} fail={fail}")
