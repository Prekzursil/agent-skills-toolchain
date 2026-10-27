#!/usr/bin/env python3
"""Shard-20 final audit: every contract dimension per unit, one pass."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "TST-0223", "TST-0227", "TST-0230", "TST-0233", "TST-0236", "TST-0238",
    "TST-0243", "TST-0245", "TST-0247", "TST-0249", "TST-0255", "TST-0256",
]
_spec = importlib.util.spec_from_file_location(
    "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules["gate"] = gate
_spec.loader.exec_module(gate)

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by_id = {u["id"]: u for u in cat["work_units"]}

print(f"{'unit':10} {'state':8} {'schema':13} {'sentinel':9} {'verdict':8} indep  sha  owner-gated")
all_ok = True
for uid in UNITS:
    rp = REPO / "command-center" / "receipts" / f"{uid}.json"
    text = rp.read_text(encoding="utf-8")
    d = json.loads(text)
    errs = gate.validate_receipt(d)
    rev = d.get("reviewer") or {}
    state = d.get("state")
    sent_ok = by_id[uid].get("completion_sentinel", "SUCCESS:" + uid) in text
    raw = rp.read_bytes().replace(b"\r\n", b"\n")
    live = hashlib.sha256(raw).hexdigest()
    man = json.loads((REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json")
                     .read_text(encoding="utf-8"))
    rel = f"command-center/receipts/{uid}.json"
    sha_ok = any(isinstance(a, dict) and a.get("unit_id") == uid
                 and str(a.get("path", "")).replace("\\", "/") == rel
                 and a.get("sha256") == live and a.get("present") is True
                 for a in man.get("artifacts") or [])
    og = by_id[uid].get("owner_approval_required")
    schema_ok = not errs
    closure_ok = rev.get("verdict") == "PASS" and rev.get("independent") is True
    ok = schema_ok and sent_ok and sha_ok and closure_ok and state == "SUCCESS"
    if not ok:
        all_ok = False
    print(f"{uid:10} {state:8} {'clean' if schema_ok else 'DIRTY':13} "
          f"{'ok' if sent_ok else 'MISS':9} {str(rev.get('verdict')):8} "
          f"{str(rev.get('independent')):6} {'ok' if sha_ok else 'BAD':4} {str(og):12}")
print("ALL-12-CONTRACT-OK" if all_ok else "PROBLEMS-REMAIN")
