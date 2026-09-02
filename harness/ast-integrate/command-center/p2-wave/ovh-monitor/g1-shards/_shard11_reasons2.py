#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
JL = HERE / "_shard11_measure.jsonl"
SH = HERE / "shard-11.txt"
ids = [ln.strip() for ln in SH.read_text(encoding="utf-8").splitlines() if ln.strip()]
rows: dict[str, dict] = {}
for ln in JL.read_text(encoding="utf-8").splitlines():
    if ln.strip():
        rec = json.loads(ln)
        rows[rec["id"]] = rec  # last wins


def tail_fail(t: str) -> str:
    lines = [x.strip() for x in (t or "").splitlines() if x.strip()]
    for ln in reversed(lines):
        if ln.startswith("FAILED:") or "Error" in ln or "Error:" in ln:
            return ln[:280]
    return (t or "")[-240:]


ok = [u for u in ids if rows.get(u, {}).get("ok")]
fail = [u for u in ids if not rows.get(u, {}).get("ok")]
print("ok", len(ok), "fail", len(fail), "unmeasured", sum(1 for u in ids if u not in rows))
print("OK", " ".join(ok))
print("FAIL", " ".join(fail))
for u in fail:
    rec = rows.get(u) or {}
    print(f"\n==== {u} {rec.get('last')}")
    print(tail_fail(rec.get("tail") or ""))
    # last 6 lines
    print(" | ".join((rec.get("tail") or "").splitlines()[-6:])[:500])
