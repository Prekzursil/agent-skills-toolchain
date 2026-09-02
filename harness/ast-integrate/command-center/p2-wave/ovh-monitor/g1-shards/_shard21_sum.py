#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ids = [
    ln.strip()
    for ln in (HERE / "shard-21.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
rows = []
for name in ("_shard21_g1_pass.jsonl", "_shard21_g1_rest.jsonl"):
    p = HERE / name
    if not p.is_file():
        continue
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
by = {r["id"]: r for r in rows}
ok = [i for i in ids if by.get(i, {}).get("ok")]
fail = [i for i in ids if i in by and not by[i].get("ok")]
miss = [i for i in ids if i not in by]
print("n", len(ids), "recorded", len(by), "ok", len(ok), "fail", len(fail), "miss", miss)
print("OK", " ".join(ok))
for i in fail:
    print("FAIL", i, (by[i].get("last") or "")[:160])
