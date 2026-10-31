#!/usr/bin/env python3
"""Counterfactual control: other program receipts must ACCEPT under the same instruments.
Proves the schema is in force and satisfiable (w4s11 precedent) - my units are stale/defective,
not victims of an unmeetable schema. Also: two-instrument cross-check on my 12 units."""
import json
import os
import sys

os.environ["AST_INTEGRATE_ROOT"] = r"C:\Users\Prekzursil\p2-g1"
REPO = r"C:/Users/Prekzursil/p2-g1"
sys.path.insert(0, REPO + "/platform/lib")
sys.path.insert(0, REPO + "/command-center")
from schema_resolver import validate_artifact  # noqa: E402
import receipt_validate  # noqa: E402

CONTROL_IDS = ["IMP-0001", "IMP-0021", "IMP-0067", "IMP-0150", "IMP-0440", "ADV-0005", "TST-0334"]
cat = json.load(open(REPO + "/command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

print("== counterfactual controls (same instruments) ==")
any_accept = False
for uid in CONTROL_IDS:
    u = byid.get(uid)
    if not u:
        print(uid, "not in catalog, skip")
        continue
    rel = str(u["output_path"]).replace("\\", "/")
    try:
        doc = json.load(open(REPO + "/" + rel, encoding="utf-8"))
    except FileNotFoundError:
        print(uid, "artifact absent on disk, skip")
        continue
    errs = validate_artifact(doc, u["output_schema"])
    v, codes, reasons = receipt_validate.admit_doc(doc, repo=REPO)
    print(f"{uid}: resolver_errors={len(errs)} admission={v} {codes[:2]}")
    if not errs and v == "ACCEPT":
        any_accept = True
print("CONTROL:", "schema is satisfiable (>=1 receipt validates)" if any_accept else "NO control receipt validated - investigate before verdicts")

print()
print("== my 12: two instruments agree? ==")
for uid in ["IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
            "IMP-0207", "IMP-0219", "IMP-0223", "IMP-0224", "IMP-0228", "IMP-0229"]:
    u = byid[uid]
    rel = str(u["output_path"]).replace("\\", "/")
    doc = json.load(open(REPO + "/" + rel, encoding="utf-8"))
    errs = validate_artifact(doc, u["output_schema"])
    v, codes, reasons = receipt_validate.admit_doc(doc, repo=REPO)
    print(f"{uid}: resolver_errors={len(errs)} admission={v} codes={codes}")
