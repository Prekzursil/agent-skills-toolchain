#!/usr/bin/env python3
"""Scratch: inspect the output_schema values + schema file shape for 3 units."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CAT = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

cat = json.loads(CAT.read_text(encoding="utf-8"))
units_list = cat.get("work_units") if isinstance(cat, dict) else cat
units = {u.get("id") or u.get("unit_id"): u for u in units_list}

for uid in ("RES-0020", "RES-0037", "RES-0044"):
    u = units[uid]
    sv = u.get("output_schema")
    print(f"### {uid} output_schema raw = {sv!r}")
    if isinstance(sv, str):
        sp = REPO / sv.replace("\\", "/")
        print(f"    exists={sp.is_file()}")
        if sp.is_file():
            s = json.loads(sp.read_text(encoding="utf-8"))
            print(f"    title={s.get('title')!r}")
            print(f"    required={s.get('required')}")
            print(f"    id/$id={s.get('$id') or s.get('id')!r}")
            props = s.get("properties") or {}
            print(f"    properties={sorted(props)[:20]}")
            print(f"    refs sample: {json.dumps({k: v for k, v in list(s.items()) if k in ('$ref',)}), }")
            defs = s.get("$defs") or s.get("definitions") or {}
            print(f"    defs={list(defs)[:10]}")
            # look for remote refs anywhere
            raw = json.dumps(s)
            import re
            refs = sorted(set(re.findall(r'"\$ref"\s*:\s*"([^"]+)"', raw)))[:12]
            print(f"    all-refs={refs}")
    print()
