#!/usr/bin/env python3
"""Schema leg via the program's own resolver: validate_artifact(doc, output_schema)."""
import json
import os
import sys

os.environ["AST_INTEGRATE_ROOT"] = r"C:\Users\Prekzursil\p2-g1"
sys.path.insert(0, r"C:\Users\Prekzursil\p2-g1\platform\lib")
from schema_resolver import validate_artifact  # noqa: E402

REPO = Path = r"C:/Users/Prekzursil/p2-g1"
mine = ["IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
        "IMP-0207", "IMP-0219", "IMP-0223", "IMP-0224", "IMP-0228", "IMP-0229"]
cat = json.load(open(REPO + "/command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}
out = {}
for uid in mine:
    u = byid[uid]
    rel = str(u["output_path"]).replace("\\", "/")
    doc = json.load(open(REPO + "/" + rel, encoding="utf-8"))
    errs = validate_artifact(doc, u["output_schema"])
    out[uid] = {"errors": errs, "count": len(errs), "output_schema": u["output_schema"]}
    print(uid, len(errs), "schema errors")
    for e in errs[:8]:
        print("   -", e[:180])
    if len(errs) > 8:
        print(f"   ... +{len(errs) - 8} more")
json.dump(out, open(r"C:/Users/Prekzursil/p2-g1/_reviewer-w4s10/schema_errors.json", "w", encoding="utf-8"), indent=1)
print("wrote schema_errors.json")
