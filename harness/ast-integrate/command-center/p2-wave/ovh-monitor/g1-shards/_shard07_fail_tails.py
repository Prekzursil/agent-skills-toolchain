#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

G = Path(__file__).resolve().parent
FAILED = re.compile(r"FAILED:[A-Z0-9-]+[^\n]{0,180}")
MOD = re.compile(r"No module named '([^']+)'")
ATTR = re.compile(r"AttributeError: ([^\n]{0,160})")
TYPE = re.compile(r"TypeError: ([^\n]{0,160})")
rows: dict[str, dict] = {}
for name in ("_shard07_g1_measure.jsonl", "_shard07_g1_remeasure.jsonl"):
    p = G / name
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            rows[rec["id"]] = rec
for uid, rec in rows.items():
    if rec.get("ok"):
        continue
    tail = rec.get("tail") or ""
    hits = FAILED.findall(tail)
    msg = hits[-1] if hits else (rec.get("last") or "")
    extra = ""
    m = MOD.search(tail)
    a = ATTR.search(tail)
    t = TYPE.search(tail)
    if m:
        extra = " ModuleNotFoundError=" + m.group(1)
    elif a:
        extra = " AttributeError=" + a.group(1)
    elif t:
        extra = " TypeError=" + t.group(1)
    print(f"{uid}: {msg}{extra}")
