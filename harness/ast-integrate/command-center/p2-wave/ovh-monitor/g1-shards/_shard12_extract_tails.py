#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

p = Path(__file__).with_name("_shard12_measure.jsonl")
for line in p.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    blob = "\n".join(r.get("tail") or [])
    hits = [
        ln.strip()
        for ln in blob.splitlines()
        if ln.strip().startswith(("FAILED:", "  FAILED:"))
        or "Error:" in ln
        or "Error:" in ln
        or "ModuleNotFound" in ln
        or "ImportError" in ln
        or "AttributeError" in ln
        or "TypeError" in ln
        or "RecursionError" in ln
    ]
    unit_hits = [h for h in hits if not h.endswith("probe-exit:1") and "FAILED:delivered" not in h]
    msg = (unit_hits[-1] if unit_hits else (hits[-1] if hits else (r.get("tail") or [""])[-2]))[:200]
    print(f"{r['id']}\t{'OK' if r.get('ok') else 'FAIL'}\t{msg}")
