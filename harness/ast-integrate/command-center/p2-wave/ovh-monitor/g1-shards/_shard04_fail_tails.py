#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
by = {}
for line in (HERE / "_shard04_measure.jsonl").read_text(encoding="utf-8").splitlines():
    if line.startswith("{"):
        rec = json.loads(line)
        by[rec["id"]] = rec
for uid in IDS:
    rec = by[uid]
    if rec.get("ok"):
        continue
    tail = rec.get("tail") or ""
    inner = []
    for ln in tail.splitlines():
        s = ln.strip()
        if s.startswith("FAILED:") or "Error" in s or s.startswith("ModuleNotFound") or s.startswith("AttributeError") or s.startswith("ImportError") or s.startswith("TypeError") or s.startswith("FileNotFound") or s.startswith("TIMEOUT") or "manifest-sha" in s:
            inner.append(s[:180])
    pick = inner[-2] if len(inner) >= 2 else (inner[-1] if inner else rec.get("last"))
    print(f"{uid}\t{pick}")
