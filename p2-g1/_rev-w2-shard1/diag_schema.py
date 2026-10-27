#!/usr/bin/env python3
"""Diagnose: which schema file does each unit declare, and what dialect is it?"""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = [
    "ADV-0037", "ADV-0038", "ADV-0040", "ADV-0090", "ADV-0091", "ADV-0096",
    "ADV-0100", "ADV-0109", "ADV-0110", "ADV-0117", "ADV-0119", "ADV-0123",
]
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wu = {x["id"]: x for x in cat["work_units"]}
for uid in IDS:
    u = wu[uid]
    srel = str(u["output_schema"]).replace("\\", "/")
    sp = REPO / srel
    s = json.loads(sp.read_text(encoding="utf-8")) if sp.is_file() else {}
    print(f"{uid}: schema={srel}")
    print(f"   draft={s.get('$schema')} id={s.get('$id')} title={s.get('title')}")

# The estate's own resolver on the same artifacts
print("\n=== platform/lib/schema_resolver.validate_artifact ===")
import sys
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver  # noqa: E402

for uid in IDS:
    u = wu[uid]
    art_rel = str(u["output_path"]).replace("\\", "/")
    art = REPO / art_rel
    try:
        res = schema_resolver.validate_artifact(art, str(u["output_schema"]))
    except Exception as exc:  # noqa: BLE001
        res = f"resolver-raise {type(exc).__name__}: {exc}"
    print(f"{uid}: {res}")
