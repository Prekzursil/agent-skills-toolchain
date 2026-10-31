#!/usr/bin/env python3
"""Shard-20: program-wide receipt-state census for the owner's 2007-green question."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
states = Counter()
missing = 0
unparsed = 0
for p in (REPO / "command-center" / "receipts").glob("*.json"):
    uid = p.stem
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        unparsed += 1
        continue
    states[str(d.get("state") or "<none>")] += 1
print("receipt files counted:", sum(states.values()), "| unparsed:", unparsed)
for s, n in states.most_common():
    print(f"  {s:12} {n}")

# catalog size for the denominator
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
print("catalog units:", len(cat["work_units"]))
