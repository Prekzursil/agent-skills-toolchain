#!/usr/bin/env python3
"""Family-matched drift control (reviewer w4s15).

Compare my 12 units' strict artifact-class conformance ONLY against
already-closed RES-family units carrying the SAME declared schema classes
(research-claim-record / measurement-run / research-registry / gem-candidate).
Like-with-like, per single-signal-verification rule 3c: a control that cannot
distinguish the two hypotheses is not a control.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
os.environ.setdefault("AST_INTEGRATE_ROOT", str(REPO))

from schema_resolver import validate_artifact  # noqa: E402

MY_12 = {
    "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
    "RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157",
}
MY_CLASSES = {}

catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in catalog.get("work_units", []) if isinstance(u, dict)}
for uid in MY_12:
    MY_CLASSES[uid] = byid[uid]["output_schema"]

wanted_classes = set(MY_CLASSES.values())

receipts_dir = REPO / "command-center" / "receipts"
family_closed = []
for rp in sorted(receipts_dir.glob("RES-*.json")):
    uid = rp.stem
    if uid in MY_12:
        continue
    try:
        r = json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        continue
    rev = r.get("reviewer") or {}
    if not (r.get("state") == "SUCCESS" and rev.get("verdict") == "PASS" and rev.get("independent") is True):
        continue
    cu = byid.get(uid)
    if not cu:
        continue
    if cu.get("output_schema") not in wanted_classes:
        continue
    if not (REPO / str(cu.get("output_path", "")).replace("\\", "/")).is_file():
        continue
    family_closed.append(uid)

print(f"family-matched closed RES units (same schema classes, other shards): {len(family_closed)}")
fail = 0
checked = 0
fail_ids = []
for uid in family_closed:
    cu = byid[uid]
    rel = str(cu["output_path"]).replace("\\", "/")
    try:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        errs = validate_artifact(doc, str(cu["output_schema"]))
    except Exception:
        continue
    checked += 1
    if errs:
        fail += 1
        fail_ids.append(uid)
print(f"family census: {fail}/{checked} fail strict artifact-class validation (same classes)")
print("sample failing family ids:", fail_ids[:10])

# error-type comparison on one family unit vs one of mine
for uid in (fail_ids[:1] + ["RES-0112"]):
    cu = byid[uid]
    rel = str(cu["output_path"]).replace("\\", "/")
    doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
    errs = validate_artifact(doc, str(cu["output_schema"]))
    print("---", uid, cu["output_schema"].split("/")[-1], "errors:", len(errs))
    for e in errs[:3]:
        print("   ", e[:200])

out = {"family_closed_total": len(family_closed), "checked": checked, "fail": fail, "failing_sample": fail_ids[:20]}
(REPO / "_reviewer-w4s15" / "family_census.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
print("SUCCESS:w4s15 family census recorded")
