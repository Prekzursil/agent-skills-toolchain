#!/usr/bin/env python3
"""Emit explicit PASS/FAIL verdicts for wave-3 shard-13 (12 IMP units).

Reads the raw verify output (_review_w3s13_out.json) and writes the
reviewer closure record: verdict + precise failing checks per unit.
Receipts are NOT modified - FAIL stays open; the single PASS confirms an
existing valid closure (receipt stays SUCCESS).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
RAW = REPO / "_review_w3s13_out.json"
OUT = REPO / "_review_w3s13_closures.json"

raw = json.loads(RAW.read_text(encoding="utf-8"))

closures = {
    "reviewer": "wave-3-shard-13-independent-reviewer (claude opus-5-5, fresh context)",
    "date": "2026-10-26",
    "scope": "12 units of _shard13-w3-entries.json "
             "(IMP-0321, 0329, 0355, 0360, 0371, 0374, 0390, 0402, 0409, 0415, 0421, 0423)",
    "transport_independence": (
        "all checks re-derived from bytes via direct sys.executable subprocess; "
        "schema validated via platform/lib/schema_resolver.validate_artifact "
        "against each unit's DECLARED output_schema string; instrument control: "
        "sibling-PASSed IMP-0074 and GREEN IMP-0299 validate at 0 violations "
        "under the same transport"
    ),
    "units": {},
}
for uid, r in raw.items():
    ok = r["ok"]
    info = r["info"]
    closures["units"][uid] = {
        "verdict": "PASS" if ok else "FAIL",
        "receipt_state": info.get("receipt_state"),
        "reviewer_independent_true": info.get("reviewer_independent"),
        "failing_checks": r["fails"] if not ok else [],
        "evidence": {
            "artifact_bytes": info.get("bytes"),
            "sha256_lf_normalized": info.get("sha256"),
            "probe_rcs": {k: v for k, v in info.items() if k.startswith("probe_")},
            "canonical_gate": info.get("gate"),
            "schema": info.get("schema"),
            "schema_violation_count": info.get("schema_violations_n", 0),
            "schema_violations_first8": info.get("schema_violations", []),
            "manifest_rows": info.get("manifest_rows"),
            "manifest_supporting_drift": info.get("manifest_supporting_drift", []),
            "receipt_reviewer_id": info.get("reviewer_id"),
        },
        "closure_action": (
            "existing PASS closure confirmed, receipt stays SUCCESS" if ok
            else "receipt unchanged; unit stays open pending rebuild - "
                 "artifact violates its catalog-declared output_schema"
        ),
    }

closures["summary"] = {
    "pass": sorted(u for u, r in closures["units"].items() if r["verdict"] == "PASS"),
    "fail": sorted(u for u, r in closures["units"].items() if r["verdict"] == "FAIL"),
    "all_ok": all(r["ok"] for r in raw.values()),
    "fail_cause": "all 11 failures are output_schema violations; every other "
                  "check (artifact parse/sentinel, manifest sha match, live "
                  "probe re-run exit 0, canonical gate SUCCESS:delivered, "
                  "receipt closure) held on all 12",
}

OUT.write_text(json.dumps(closures, indent=1, ensure_ascii=False) + "\n",
               encoding="utf-8", newline="\n")
print("wrote", OUT)
for uid in sorted(closures["units"]):
    u = closures["units"][uid]
    n = u["evidence"]["schema_violation_count"]
    print(uid, u["verdict"],
          ("| schema-violations=%d" % n) if u["failing_checks"] else "| all-checks-hold")
s = closures["summary"]
print(("SUCCESS:" if s["all_ok"] else "FAILED:")
      + "w3s13 closures emitted 12 units, pass=%d fail=%d"
      % (len(s["pass"]), len(s["fail"])))
