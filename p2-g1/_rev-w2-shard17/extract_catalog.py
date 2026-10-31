#!/usr/bin/env python3
"""Shard-17 w2 reviewer scratch: slice the 12 catalog entries out of WORK-UNIT-CATALOG.json."""
import json
from pathlib import Path

IDS = [
    "RES-0020", "RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079",
    "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
]
CAT = Path(r"C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json")
OUT = Path(r"C:\Users\Prekzursil\p2-g1\_rev-w2-shard17\catalog-slice.json")

cat = json.loads(CAT.read_text(encoding="utf-8"))
units = None
if isinstance(cat, dict):
    for key in ("work_units", "units", "entries", "catalog"):
        val = cat.get(key)
        if isinstance(val, list):
            units = val
            break
    if units is None:
        units = cat
else:
    units = cat
if isinstance(units, list):
    units = {u.get("id") or u.get("unit_id"): u for u in units}

out = {}
for uid in IDS:
    if uid in units:
        out[uid] = units[uid]
missing = [u for u in IDS if u not in out]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("SLICED:", len(out), "MISSING:", missing)
for uid in sorted(out):
    e = out[uid]
    print(f"{uid} | output_path={e.get('output_path')} | sentinel={e.get('completion_sentinel')!r} | probes={e.get('probes')} | deps={e.get('dependencies')}")
