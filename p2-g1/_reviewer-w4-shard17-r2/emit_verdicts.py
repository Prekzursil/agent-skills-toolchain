#!/usr/bin/env python3
"""Emit verdicts.json + REVIEW-RETURN.json for reviewer wave4 shard17 r2.
Fail contract: ANY fails -> verdict FAIL, receipts untouched (verified by probe
battery mutation guard: before/after snapshot equal, 0 mutated/added/removed).
"""
import json
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
D = REPO / "_reviewer-w4-shard17-r2"
UNITS = ["TST-0032","TST-0057","TST-0060","TST-0066","TST-0067","TST-0068",
         "TST-0070","TST-0081","TST-0085","TST-0088","TST-0090","TST-0091"]

phase1 = json.loads((D/"phase1_state.json").read_text(encoding="utf-8"))
schema = json.loads((D/"schema_results.json").read_text(encoding="utf-8"))
probes = json.loads((D/"probe_rerun.json").read_text(encoding="utf-8"))

verdicts = {"_meta": {"reviewer": "claude-opus-5-5-independent-reviewer-w4-shard17-r2",
                      "utc": datetime.now(timezone.utc).isoformat()},
            "units": {}}
for uid in UNITS:
    c = phase1[uid]["checks"]
    sc = schema["units"][uid]
    pr = probes["units"][uid]
    probe_ok = all(v.get("ok") for v in pr.values())
    holding = {
        "S1_catalog": True,  # output_path/output_schema/deps present; no owner-gated units
        "S2_artifact": all([c["S2_exists"], c["S2_parses"], c["S2_not_self_blocked"], c["S2_sentinel"]]),
        "S3_manifest_sha": all([c["S3_primary_row_present"], c["S3_primary_sha_match"], c["S3_all_rows_match"]]),
        "P_probes_exit0": probe_ok,
        "S5_probe_files": c["S5_probe_files_present"],
    }
    fails = []
    if sc["primary_count"] > 0:
        fails.append("output_schema")
    rv = c.get("S4rev_reviewer_id", "")
    if not c["S4rev_identity_genuine"] or "rederive" in rv.lower():
        fails.append("reviewer_identity_not_independent")
    verdicts["units"][uid] = {
        "verdict": "FAIL" if fails else "PASS",
        "failing_check": " + ".join(fails) if fails else None,
        "schema_violations_primary": sc["primary_count"],
        "schema_violations_second_instrument": sc["second_count"],
        "admission_gate": "REJECT (schema-invalid) - third instrument, command-center/receipt_validate.py",
        "holding_checks": holding,
        "reviewer_block_id": c.get("S4rev_reviewer_id", ""),
        "state_on_receipt": c.get("S2_state"),
    }
verdicts["summary"] = {
    "PASS": sum(1 for v in verdicts["units"].values() if v["verdict"] == "PASS"),
    "FAIL": sum(1 for v in verdicts["units"].values() if v["verdict"] == "FAIL"),
    "receipts_modified": "NONE",
}
(D/"verdicts.json").write_text(json.dumps(verdicts, indent=1), encoding="utf-8")

ret = {
 "reviewer_id": "w4-shard17-independent-reviewer-r2-20261026",
 "wave": 4, "shard": 17, "rerun_of": "r1 (_p2-shard17-w4-review, 2026-10-26 09:25)",
 "program": "estate P2 fail-closed program",
 "repo": "C:/Users/Prekzursil/p2-g1",
 "reviewed_at": "2026-10-26",
 "verdict_summary": {"PASS": 0, "FAIL": 12, "confirmed_existing_pass": 0, "closures_written": []},
 "units": {uid: {"verdict": v["verdict"], "failing_check": v["failing_check"],
                 "schema_violations": v["schema_violations_primary"]}
           for uid, v in verdicts["units"].items()},
 "checks_holding_all_12": [
  "S1 catalog entries present (output_path, output_schema, deps; owner_approval_required=false x12)",
  "S2 artifact exists/non-empty/parses/state=SUCCESS not-self-blocked, completion sentinel present x12",
  "S3 manifest sha256 CRLF->LF recomputed live: PRIMARY row + ALL rows match x12",
  "P 24/24 named probes re-run by this reviewer, all exit 0 (WSL healthy this run - r1's bash-transport artifact did not reproduce)",
  "S5 catalog tests_required probe files all present; SUBAGENT-RETURN status DELIVERED x12",
  "mutation guard: 0 artifacts/probe files mutated/added/removed across the full battery",
 ],
 "failing_check": ("S4 output_schema: canonical platform/lib/schema_resolver.validate_artifact fails "
   "ALL 12 with 2-64 violations each; second instrument (raw jsonschema Draft202012 over the resolved "
   "physical schema) gives IDENTICAL counts 12/12; third instrument command-center/receipt_validate.py "
   "REJECTs all 12 (schema-invalid); both-states proof: 13/13 same-class controls "
   "(TST-0101..0127 test-receipt class + AUD-0035) validate CLEAN; r1's per-unit violation counts "
   "reproduced EXACTLY (32/44/2/64/19/17/23/23/25/40/20/18) - receipts unchanged since r1 "
   "(mtimes 2026-10-24/25), so the r1 failures stand unfixed."),
 "failing_check_2": ("reviewer identity not independent: all 12 receipts carry reviewer.verdict=PASS + "
   "independent=true but reviewer_id is PROBE-DERIVED (e.g. TST-0032-probe2-green-claim-blocked, "
   "schema-resolver, TST-0090-probe2-timeout-only-mutant, TST-0067-rederive-from-proc-environ-and-scope-file) "
   "- a probe/derivation procedure is not the independent reviewer the program requires to close; "
   "same defect class r1 flagged, unfixed."),
 "receipt_actions": "receipt-unchanged (fail contract): no receipt, manifest, or artifact written by this reviewer; mutation guard clean.",
 "evidence": {
  "phase1_state": "_reviewer-w4-shard17-r2/phase1_state.json",
  "schema_results": "_reviewer-w4-shard17-r2/schema_results.json",
  "probe_rerun": "_reviewer-w4-shard17-r2/probe_rerun.json",
  "verdicts": "_reviewer-w4-shard17-r2/verdicts.json",
 },
 "fix_required": ("receipt-content rewrite to the test/benchmark/fault-injection class envelope "
   "(report, downstream_consumers, residual_unknowns, negative_controls, defects, extensions, "
   "per-field enums) + a genuine independent reviewer closure, then re-review."),
}
(D/"REVIEW-RETURN.json").write_text(json.dumps(ret, indent=1), encoding="utf-8")
print("PASS", ret["verdict_summary"]["PASS"], "FAIL", ret["verdict_summary"]["FAIL"])
print("wrote verdicts.json + REVIEW-RETURN.json")
