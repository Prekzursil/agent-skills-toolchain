#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (HERE / "shard-03.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
live = json.loads((HERE / "_shard03_live.json").read_text(encoding="utf-8"))
fin = json.loads((HERE / "_shard03_finish.json").read_text(encoding="utf-8"))
by = {r["id"]: r for r in live["rows"]}
by.update({r["id"]: r for r in fin["rows"]})
# later remesure, this session, last line SUCCESS:delivered WFA-0110
by["WFA-0110"] = {
    "id": "WFA-0110",
    "ok": True,
    "rc": 0,
    "line": "SUCCESS:delivered WFA-0110",
    "tail": "artifact command-center/wfa/WFA-0110-fusion-lineage-and-rollback.json bytes=36714 sha256=8cfb90ce732aba2e43b839783d0134c99a3d788aa7f9f7f04401101add97f0e3\nSUCCESS:delivered WFA-0110",
}

def probe_fail(tail: str) -> str:
    hits = []
    for ln in (tail or "").splitlines():
        s = ln.strip()
        if s.startswith("FAILED:") and "delivered" not in s:
            hits.append(s[:180])
        if "Error:" in s or s.startswith("ModuleNotFoundError") or s.startswith("AttributeError") or s.startswith("TypeError") or s.startswith("KeyError"):
            hits.append(s[:180])
    return hits[-1] if hits else ""

print(f"{'ID':10} {'G1':8} probe-fail")
okn = failn = 0
for uid in IDS:
    rec = by[uid]
    line = rec.get("line") or ""
    ok = rec.get("ok") is True and line.startswith("SUCCESS:delivered ")
    if ok:
        okn += 1
        print(f"{uid:10} OK       {line}")
    else:
        failn += 1
        print(f"{uid:10} FAIL     {probe_fail(rec.get('tail') or '') or line}")
print(f"attempted={len(IDS)} ok={okn} fail={failn}")
