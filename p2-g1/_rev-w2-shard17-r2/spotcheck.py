#!/usr/bin/env python3
"""Spot-check the actual violating fragments vs clean same-class siblings."""
import json
import pathlib
import sys

REPO = pathlib.Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as SR

a = json.loads((REPO / "command-center/research/RES-0020.json").read_text(encoding="utf-8"))
print("RES-0020 top keys:", sorted(a.keys()))
print("RES-0020 reviewer keys:", sorted((a.get("reviewer") or {}).keys()))

b = json.loads((REPO / "command-center/research/RES-0049.json").read_text(encoding="utf-8"))
ev = (b.get("evidence") or [{}])[0]
print("RES-0049 top keys:", sorted(b.keys()))
print("RES-0049 evidence[0] keys:", sorted(ev.keys()))

c = json.loads((REPO / "command-center/research/RES-0111.json").read_text(encoding="utf-8"))
ev1 = (c.get("evidence") or [{}])[0]
print("RES-0111 evidence[0] keys:", sorted(ev1.keys()))

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}
for uid in ["RES-0005", "RES-0007", "RES-0008", "RES-0030", "RES-0047"]:
    u = units.get(uid)
    if not u:
        continue
    p = REPO / str(u["output_path"]).replace("\\", "/")
    if not p.is_file():
        print(f"{uid}: artifact absent")
        continue
    doc = json.loads(p.read_text(encoding="utf-8"))
    errs = SR.validate_artifact(doc, u["output_schema"])
    e0 = (doc.get("evidence") or [{}])[0]
    print(f"{uid}: class-clean violations={len(errs)} top-keys={sorted(doc.keys())[:12]} "
          f"evidence[0] keys={sorted(e0.keys())}")
