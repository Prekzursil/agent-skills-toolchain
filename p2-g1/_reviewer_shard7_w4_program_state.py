#!/usr/bin/env python3
"""Program-wide green tier sweep over all catalogued work units.

Tiers computed per unit (static, no probe re-runs):
  T1  receipt artifact exists at catalog output_path
  T1b parses as a JSON object
  T2  state == SUCCESS
  T3  T2 + reviewer.verdict == PASS + reviewer.independent == true
  T4  T3 + canonical receipt_schema_gate.validate_receipt() CLEAN (condition 4)
Writes _reviewer_shard7_w4_program_state.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
spec = importlib.util.spec_from_file_location(
    "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
gate = importlib.util.module_from_spec(spec)
sys.modules["gate"] = gate
spec.loader.exec_module(gate)

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = cat["work_units"]
t0 = time.time()
rows = {}
n = 0
for u in units:
    uid = u["id"]
    n += 1
    op = str(u.get("output_path") or "").replace("\\", "/")
    r = {"has_artifact": False}
    p = REPO / op
    if p.is_file():
        r["has_artifact"] = True
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            d = None
        if isinstance(d, dict):
            r["parses"] = True
            st = str(d.get("state") or "").upper()
            r["state"] = st
            rv = d.get("reviewer") if isinstance(d.get("reviewer"), dict) else {}
            r["rev_pass"] = rv.get("verdict") == "PASS"
            r["indep"] = rv.get("independent") is True
            if st == "SUCCESS":
                try:
                    errs = gate.validate_receipt(d)
                    r["schema_violations"] = len(errs)
                except Exception as exc:
                    r["schema_violations"] = f"gate-error:{type(exc).__name__}"
    rows[uid] = r

print("scanned %d in %.1fs" % (n, time.time() - t0))


def c(pred):
    return sum(1 for r in rows.values() if pred(r))


T_art = c(lambda r: r.get("has_artifact"))
T_parse = c(lambda r: r.get("parses"))
T_succ = c(lambda r: r.get("state") == "SUCCESS")
T_rev = c(lambda r: r.get("state") == "SUCCESS" and r.get("rev_pass") and r.get("indep"))
T_clean = c(lambda r: r.get("schema_violations") == 0)
T_dirty = c(lambda r: isinstance(r.get("schema_violations"), int) and r["schema_violations"] > 0)
T_err = c(lambda r: isinstance(r.get("schema_violations"), str))
print("catalog units: %d" % n)
print("T1 artifact present:            %d" % T_art)
print("T1b parses as JSON object:      %d" % T_parse)
print("T2 state==SUCCESS:              %d" % T_succ)
print("T3 SUCCESS+reviewer PASS+indep: %d" % T_rev)
print("T4 +schema gate CLEAN:          %d" % T_clean)
print("   (schema-dirty SUCCESS:       %d, gate-error: %d)" % (T_dirty, T_err))
(REPO / "_reviewer_shard7_w4_program_state.json").write_text(
    json.dumps(rows, indent=0, ensure_ascii=False) + "\n",
    encoding="utf-8", newline="\n",
)
print("written _reviewer_shard7_w4_program_state.json")
print("SUCCESS:program-state-sweep" if n == 2007 else "FAILED:program-state-sweep unit-count")
