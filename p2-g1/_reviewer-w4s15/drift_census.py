#!/usr/bin/env python3
"""Independent drift census + second-instrument receipt check (reviewer w4s15).

Question 1 (census): is artifact-vs-class-profile strict non-conformance
program-wide historical drift (live schema tightened after emission), or unique
to my 12 units? Sample already-CLOSED units (state=SUCCESS, independent PASS)
owned by OTHER shards and count strict validation failures with MY instrument.
  - If the sampled closed units fail at a comparable rate, the drift is
    program-wide historical => census, not per-unit gating (w3s16 precedent,
    which measured 508/1062).
  - If my 12 fail while closed units are clean, that is a REAL content defect.

Question 2 (two instruments on the receipt): my battery used a hand-built
receipt_core validator; cross-check 0-error with the program gate
receipt_schema_gate.validate_receipt (mechanically different loader).
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
os.environ.setdefault("AST_INTEGRATE_ROOT", str(REPO))

from schema_resolver import validate_artifact  # noqa: E402
from receipt_schema_gate import load_schema, validate_receipt  # noqa: E402

MY_12 = [
    "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
    "RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157",
]

catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in catalog.get("work_units", []) if isinstance(u, dict)}

# ---- collect already-closed units (SUCCESS + independent PASS), excluding MY_12
closed = []
receipts_dir = REPO / "command-center" / "receipts"
for rp in sorted(receipts_dir.glob("*.json")):
    uid = rp.stem
    if uid in MY_12:
        continue
    try:
        r = json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        continue
    rev = r.get("reviewer") or {}
    if r.get("state") == "SUCCESS" and rev.get("verdict") == "PASS" and rev.get("independent") is True:
        cu = byid.get(uid)
        if cu and (REPO / str(cu.get("output_path", "")).replace("\\", "/")).is_file():
            closed.append(uid)

print(f"closed-with-artifact population (excluding my 12): {len(closed)}")
random.seed(20261026)
sample = random.sample(closed, min(40, len(closed)))

closed_fail = 0
closed_total = 0
for uid in sample:
    cu = byid[uid]
    rel = str(cu["output_path"]).replace("\\", "/")
    try:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        errs = validate_artifact(doc, str(cu["output_schema"]))
    except Exception:
        continue
    closed_total += 1
    if errs:
        closed_fail += 1
if closed_total:
    print(f"census: {closed_fail}/{closed_total} sampled already-closed units ALSO fail strict artifact-class validation")

# ---- my 12 strict counts (from battery)
mine_fail = 0
for uid in MY_12:
    cu = byid[uid]
    rel = str(cu["output_path"]).replace("\\", "/")
    doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
    errs = validate_artifact(doc, str(cu["output_schema"]))
    if errs:
        mine_fail += 1
print(f"my 12: {mine_fail}/12 fail strict artifact-class validation")

verdict = "PROGRAM-WIDE HISTORICAL DRIFT (census, non-gating)" if closed_total >= 20 and closed_fail / closed_total >= 0.5 else ("MIXED/INCONCLUSIVE" if closed_fail else "MY-12-UNIQUE (gating defect)")
print("CENSUS VERDICT:", verdict)

# ---- second instrument: program receipt gate on all 12 receipts
sch = load_schema(REPO / "platform" / "schema" / "receipt.schema.json")
gate_ok = 0
for uid in MY_12:
    r = json.loads((REPO / "command-center" / "receipts" / (uid + ".json")).read_text(encoding="utf-8"))
    errs = validate_receipt(r, schema=sch)
    if not errs:
        gate_ok += 1
    else:
        print(f"  program-gate receipt errors {uid}: {errs[:2]}")
print(f"program-gate receipt validation: {gate_ok}/12 receipts 0-error")

out = {
    "census_population": len(closed),
    "census_sampled": closed_total,
    "census_fail": closed_fail,
    "my12_strict_fail": mine_fail,
    "verdict": verdict,
    "program_gate_receipt_ok": gate_ok,
}
(REPO / "_reviewer-w4s15" / "census_results.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
print("SUCCESS:w4s15 census recorded")
