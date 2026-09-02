#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

p = Path(__file__).with_name("_shard04_measure.jsonl")
for line in p.read_text(encoding="utf-8").splitlines():
    if not line.startswith("{"):
        continue
    rec = json.loads(line)
    uid = rec["id"]
    if rec.get("ok"):
        print(f"{uid:10} OK")
        continue
    tail = rec.get("tail") or ""
    lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    picks = []
    for ln in lines:
        if re.search(r"FAILED:|Error:|Exception|ModuleNotFound|AttributeError|TypeError|FileNotFound|Unresolvable|TIMEOUT|manifest-sha|probe-exit", ln):
            picks.append(ln[:220])
    if not picks:
        picks = lines[-3:]
    print(f"{uid:10}")
    for ln in picks[-4:]:
        print(f"    {ln}")
