#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = []
for ln in (HERE / "_shard16_win_probes.jsonl").read_text(encoding="utf-8").splitlines():
    if ln.strip():
        rows.append(json.loads(ln))
ok = [r["id"] for r in rows if r.get("ok")]
fail = [r for r in rows if not r.get("ok")]
print("ok", len(ok), ok)
print("fail", len(fail))
print()
for r in fail:
    probes = r.get("probes") or []
    last = probes[-1] if probes else {}
    tail = (last.get("tail") or last.get("last") or "")[-500:]
    print("=" * 72)
    print(r["id"], "rc", last.get("rc"), "fail", (r.get("fails") or [""])[0][:160])
    print(tail)
