#!/usr/bin/env python3
"""Estate-wide receipt admission sweep (wave-3 shard-11 reviewer side probe).

Drives command-center/receipt_validate.admit_path in-process over ALL
receipts (no argv, so the Windows env/arg limits cannot truncate the sweep).
Counts ACCEPT / REJECT and per-REJECT first reasons. Also splits by receipt
state so the 2007-green progress number separates
  state=SUCCESS + schema-valid   (delivered AND admitted)
  state=SUCCESS + schema-invalid (green-but-broken; reviewer FAIL class)
  state=BLOCKED / other
Writes detail to _estate_receipt_admission_w3s11.json.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
RV = REPO / "command-center" / "receipt_validate.py"
OUT = REPO / "_estate_receipt_admission_w3s11.json"

spec = importlib.util.spec_from_file_location("receipt_validate_sweep", RV)
mod = importlib.util.module_from_spec(spec)
sys.modules["receipt_validate_sweep"] = mod
spec.loader.exec_module(mod)

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
total_units = len(cat.get("work_units") or [])

rows = []
verdicts = Counter()
state_x_verdict = Counter()
reason_heads = Counter()
for p in sorted((REPO / "command-center" / "receipts").glob("*.json")):
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        state = doc.get("state")
    except Exception:
        state = "UNPARSEABLE"
    verdict, cnums, reasons = mod.admit_path(p)
    verdicts[verdict] += 1
    state_x_verdict["%s|%s" % (state, verdict)] += 1
    if verdict != "ACCEPT":
        head = reasons[0][:110] if reasons else "no-reason"
        reason_heads[head] += 1
    rows.append({"unit": p.stem, "state": state, "verdict": verdict,
                 "reasons": reasons[:3]})

summary = {
    "catalog_work_units": total_units,
    "receipt_files": len(rows),
    "verdicts": dict(verdicts),
    "state_x_verdict": dict(state_x_verdict),
    "top_reject_reasons": reason_heads.most_common(15),
}
OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n",
               encoding="utf-8")
print(json.dumps(summary, indent=1))
print("SUCCESS:estate-receipt-admission-sweep" if rows else "FAILED:estate-receipt-admission-sweep no-inputs")
