#!/usr/bin/env python3
"""C2 admission census across ALL receipts + precise fragment-schema error dump for shard-20 units."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")

# load the canonical gate the way receipt_validate.py does
spec = importlib.util.spec_from_file_location("gate", REPO / "platform/lib/receipt_schema_gate.py")
gate = importlib.util.module_from_spec(spec)
sys.modules["gate"] = gate
spec.loader.exec_module(gate)

SHARD = ["TST-0129", "TST-0130", "TST-0136", "TST-0137", "TST-0138", "TST-0139",
         "TST-0141", "TST-0142", "TST-0143", "TST-0144", "TST-0145", "TST-0150"]

rdir = REPO / "command-center/receipts"
files = sorted(rdir.glob("*.json"))
admit = 0
reject = 0
reject_ids = []
for f in files:
    try:
        doc = json.loads(f.read_bytes().decode("utf-8"))
    except Exception:
        reject += 1
        reject_ids.append(f.stem)
        continue
    errs = gate.validate_receipt(doc)
    if errs:
        reject += 1
        reject_ids.append(f.stem)
    else:
        admit += 1

print("CENSUS total=%d admitted=%d rejected=%d" % (len(files), admit, reject))
print("sample rejected:", reject_ids[:15])

# precise errors for the shard
print("--- shard detail ---")
for uid in SHARD:
    doc = json.loads((rdir / (uid + ".json")).read_bytes().decode("utf-8"))
    errs = gate.validate_receipt(doc)
    print("%s C2_ERRORS=%d" % (uid, len(errs)))
    for e in errs:
        print("   ", e[:200])
