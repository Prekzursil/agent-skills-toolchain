#!/usr/bin/env python3
"""Emit explicit PASS/FAIL verdicts for wave-3 shard-7 (12 IMP units).

Reads the raw verify output (_reviewer_shard7_w3_verdicts.json) and writes the
reviewer closure record: verdict + precise failing checks per unit. Receipts
are NOT modified - only the reviewer record is written.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
RAW = REPO / "_reviewer_shard7_w3_verdicts.json"
OUT = REPO / "_reviewer_shard7_w3_closures.json"

raw = json.loads(RAW.read_text(encoding="utf-8"))

closures = {
    "reviewer": "wave-3-shard-7-independent-reviewer (claude opus-5-5, fresh context)",
    "date": "2026-10-26",
    "scope": "12 units of _p2-shard7-catalog-extract.json (IMP-0074..IMP-0146)",
    "transport_independence": (
        "all checks re-derived from bytes via direct sys.executable subprocess; "
        "not the builder's _measure_one_delivered.py transport"
    ),
    "units": {},
}
for uid, r in raw["units"].items():
    ok = r["ok"]
    closures["units"][uid] = {
        "verdict": "PASS" if ok else "FAIL",
        "receipt_state": r["info"].get("receipt_state"),
        "failing_checks": r["fails"] if not ok else [],
        "evidence": {
            "artifact_bytes": r["info"].get("bytes"),
            "sha256_lf_normalized": r["info"].get("sha256"),
            "probe_rcs": {k: v for k, v in r["info"].items() if k.startswith("probe_")},
            "schema": r["info"].get("schema"),
        },
        "closure_action": (
            "existing PASS closure confirmed, receipt stays SUCCESS" if ok
            else "receipt unchanged; unit stays open pending rebuild"
        ),
    }

closures["summary"] = {
    "pass": sorted(u for u, r in closures["units"].items() if r["verdict"] == "PASS"),
    "fail": sorted(u for u, r in closures["units"].items() if r["verdict"] == "FAIL"),
    "all_ok": raw["all_ok"],
}

OUT.write_text(json.dumps(closures, indent=1, ensure_ascii=False) + "\n",
               encoding="utf-8", newline="\n")
print("wrote", OUT)
for uid in sorted(closures["units"]):
    u = closures["units"][uid]
    print(uid, u["verdict"], ("| " + "; ".join(f[:110] for f in u["failing_checks"][:3])) if u["failing_checks"] else "")
print(("SUCCESS:" if raw["all_ok"] else "FAILED:") + "reviewer-shard7-w3 closures emitted 12 units, pass=%d fail=%d"
      % (len(closures["summary"]["pass"]), len(closures["summary"]["fail"])))
