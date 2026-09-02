#!/usr/bin/env python3
"""Extract catalog output_path for shard-12 IDs. Not a measurement."""
from __future__ import annotations

import json
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\WORK-UNIT-CATALOG.json")
ids = [
    "ADV-0019",
    "ADV-0085",
    "ADV-0131",
    "ARC-0037",
    "ARC-0099",
    "AUD-0035",
    "AUD-0067",
    "BLD-0008",
    "BLD-0044",
    "CNF-0006",
    "CNF-0068",
    "CNF-0117",
    "CNF-0158",
    "CNL-0059",
    "CNL-0075",
    "IMP-0079",
    "IMP-0122",
    "IMP-0167",
    "IMP-0091",
    "IMP-0288",
    "IMP-0334",
    "IMP-0389",
    "IMP-0435",
    "REL-0002",
    "RES-0053",
    "RES-0111",
    "RES-0156",
    "RES-0182",
    "SYN-0036",
    "TST-0035",
    "TST-0073",
    "TST-0117",
    "TST-0162",
    "TST-0203",
    "TST-0244",
    "TST-0274",
    "TST-0308",
    "TST-0338",
    "WFA-0064",
    "WFA-0118",
]
data = json.loads(p.read_text(encoding="utf-8"))
want = set(ids)
found = {}
for u in data.get("work_units") or []:
    uid = u.get("id")
    if uid in want:
        found[uid] = {
            "output_path": u.get("output_path"),
            "completion_sentinel": u.get("completion_sentinel"),
        }
out = Path(__file__).with_name("_s12_catalog.out.json")
ordered = {i: found.get(i) for i in ids}
out.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
print("wrote", out, "found", sum(1 for v in ordered.values() if v), "of", len(ids))
