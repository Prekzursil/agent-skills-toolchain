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
by = {r["id"]: r for r in rows}
ok = [
    uid
    for uid, rec in sorted(by.items())
    if rec.get("last") == f"SUCCESS:delivered {uid}"
]
print("ok_n", len(ok))
for uid in ok:
    rec = by[uid]
    lines = [ln.rstrip() for ln in (rec.get("tail") or "").splitlines() if ln.strip()]
    keep = [ln for ln in lines if ln.startswith(("artifact ", "SUCCESS:", "probe["))]
    print("=" * 72)
    print(uid, "rc", rec.get("rc"), "last", rec.get("last"))
    for ln in keep[-8:]:
        print(ln)
