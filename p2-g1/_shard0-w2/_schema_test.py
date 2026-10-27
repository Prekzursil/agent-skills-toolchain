#!/usr/bin/env python3
"""Shard0-w2: jsonschema-validate all 12 unit artifacts against output_schema."""
import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
IDS = ["ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018", "ADV-0019",
       "ADV-0022", "ADV-0023", "ADV-0024", "ADV-0028", "ADV-0029", "ADV-0033"]

data = json.loads(CATALOG.read_text(encoding="utf-8"))
units = {u.get("id"): u for u in data.get("work_units", []) if isinstance(u, dict)}

try:
    import jsonschema
    print("jsonschema", jsonschema.__version__)
except ImportError:
    print("jsonschema MISSING")
    raise SystemExit(1)

for uid in IDS:
    u = units.get(uid) or {}
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    schema_rel = str(u.get("output_schema") or "").replace("\\", "/")
    try:
        doc = json.loads((REPO / out_rel).read_text(encoding="utf-8"))
        schema = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
        errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc),
                      key=lambda e: str(list(e.absolute_path)))
        print(f"{uid}: errors={len(errs)}")
        for e in errs[:3]:
            print(f"   {list(e.absolute_path)}: {str(e.message)[:160]}")
    except Exception as exc:
        print(f"{uid}: ERROR {type(exc).__name__}: {str(exc)[:160]}")
