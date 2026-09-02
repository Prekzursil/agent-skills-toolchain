#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = [
    json.loads(ln)
    for ln in (HERE / "_shard15_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
by = {r["id"]: r for r in rows}
ok_ids = [
    "ADV-0077",
    "ADV-0122",
    "CNL-0089",
    "IMP-0052",
    "IMP-0076",
    "IMP-0101",
    "IMP-0244",
    "IMP-0398",
    "IMP-0466",
    "SYN-0020",
    "TST-0110",
    "TST-0142",
    "TST-0211",
    "WFA-0089",
]
print("jsonl_n", len(rows))
for uid in ok_ids:
    rec = by[uid]
    tail = rec.get("tail") or ""
    last_ok = rec.get("last") == f"SUCCESS:delivered {uid}"
    art = ""
    for ln in tail.splitlines():
        if ln.startswith("artifact ") or "SUCCESS:delivered" in ln:
            art = ln.strip()
    print(f"OK {uid} last_ok={last_ok} rc={rec.get('rc')} close={art[-160:]}")
fp = hashlib.sha256(
    (HERE / "shard-15.remaining.txt").read_bytes().replace(b"\r\n", b"\n")
).hexdigest()
print("remaining_fp", fp, "n", sum(1 for ln in (HERE / "shard-15.remaining.txt").read_text(encoding="utf-8").splitlines() if ln.strip()))
