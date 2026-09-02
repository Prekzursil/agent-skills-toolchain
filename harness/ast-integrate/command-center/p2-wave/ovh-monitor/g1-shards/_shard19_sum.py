#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "_shard19_win_probes.jsonl"
rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
print("n", len(rows), "ok", sum(1 for r in rows if r.get("ok")), "fail", sum(1 for r in rows if not r.get("ok")))
out = []
for r in rows:
    mark = "OK" if r.get("ok") else "FAIL"
    fail = (r.get("fails") or [""])[0]
    print(f"{mark} {r['id']} {fail[:240]}")
    rec = {
        "id": r["id"],
        "ok": r.get("ok"),
        "fails": r.get("fails"),
        "probes": [],
    }
    for pr in r.get("probes") or []:
        rec["probes"].append(
            {
                "i": pr.get("i"),
                "rc": pr.get("rc"),
                "last": (pr.get("last") or "")[:300],
                "tail": (pr.get("tail") or "")[-1800:],
            }
        )
    out.append(rec)
(HERE / "_shard19_fail_tails.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("wrote tails")
