#!/usr/bin/env python3
"""Write the reviewer verdict summary for wave 2 shard 17 (2026-10-26 run)."""
import json
import pathlib
from datetime import datetime, timezone

REPO = pathlib.Path(r"C:\Users\Prekzursil\p2-g1")
ev = json.loads((REPO / "_rev-w2-shard17-r2/verify-evidence-r2.json").read_text(encoding="utf-8"))
UNITS = ["RES-0020", "RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079",
         "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111"]

per_unit = {}
for uid in UNITS:
    u = ev["units"][uid]
    schema_fails = [f for f in u["fails"] if f.startswith("schema-")]
    other_fails = [f for f in u["fails"] if not f.startswith("schema-")]
    per_unit[uid] = {
        "verdict": "FAIL" if schema_fails else ("PASS" if not u["fails"] else "FAIL"),
        "failing_check": "output_schema validation" if schema_fails else None,
        "schema_violations": u.get("schema_resolver"),
        "schema_direct": u.get("schema_direct"),
        "non_schema_fails": other_fails,
        "artifact_sha256_lf": u.get("sha256"),
        "manifest_sha_match": not any(f.startswith("manifest-") for f in u["fails"]),
        "probes_green": not any(f.startswith("probe-") for f in u["fails"]),
        "artifact_state": u.get("artifact_state"),
        "receipt_state_unchanged": "BLOCKED",
    }

summary = {
    "reviewer": "independent-reviewer-shard17-w2-r2-20261026",
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "units": len(UNITS),
    "fail": len([1 for v in per_unit.values() if v["verdict"] == "FAIL"]),
    "pass": len([1 for v in per_unit.values() if v["verdict"] == "PASS"]),
    "receipts_modified": 0,
    "sole_failing_check": "output_schema validation (blessed resolver AND direct jsonschema agree)",
    "g1_delivered_measure_run_by_reviewer": "SUCCESS:delivered for all 12 (predicate green)",
    "schema_satisfiability_control": "51 research-claim-record + 44 measurement-run catalog RES artifacts "
                                    "validate clean with the same instrument (population control, re-run "
                                    "from _rev-w2-shard17/reverify_battery.py population)",
    "closure_withheld_because": "checklist requires ALL checks incl. output_schema to hold; "
                               "a PASS over a real schema violation would be a dishonest PASS",
    "per_unit": per_unit,
}
dst = REPO / "_rev-w2-shard17-r2" / "VERDICT-SUMMARY.json"
dst.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
print("WROTE:", dst)
print(json.dumps({k: v for k, v in summary.items() if k != "per_unit"}, indent=1))
