#!/usr/bin/env python3
"""Write the shard-24 r2 final review report (closures + failures)."""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard24-w2-review"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

fails = {
 "TST-0151": {
  "verdict": "FAIL", "receipt_unchanged": True,
  "fail_reasons": [
   "R2: receipt_core-FAILED-sentinel-with-SUCCESS: sentinel='FAILED:TST-0151 refute rerun does not falsify the isolated detector; production integration, condition 11, and Windows review remain blocked'",
   "R3b: cond10-open-P0/P1-defect:TST-0151-D1 (P1 open: process-owned detector isolated to probe dir; scripts/longrun.sh still wrapper-owned)",
   "R3b: manifest_registration.registered=false (explicit negative assertion on a SUCCESS receipt)",
   "R3b: SUCCESS-test-row-FAIL: tests[3] result=FAIL",
   "R6: probe2 rc=1 receipt-contract-drift: probe reads doc['detector_control']['sequence']; key absent from receipt (art=None); native-WSL probe1 rc=0"
  ],
  "notes": "probe1 passes on native Linux fs (idle-alive-silent / SIGSTOP-flips / mutant fires). Schema ENVELOPE-DRIFT (content 0) - non-gating, recorded."
 },
 "TST-0158": {
  "verdict": "FAIL", "receipt_unchanged": True,
  "fail_reasons": [
   "R6: probe1 rc=1 FAILED:TST-0158-probe1 artifact merger_signal.collision_ids != live CLI list (recorded evidence no longer reproduces; tools/command-center/merge_catalog.py drifted 7885B -> 19237B vs manifest row)",
   "R6: probe2 rc=1 FAILED:TST-0158-probe2 artifact independent_intersection.ids != live set-intersection",
   "R2: receipt_core-FAILED-sentinel-with-SUCCESS: sentinel='FAILED:TST-0158 merger accepts 31 colliding ids without a list; condition 11 live-red'",
   "R3b: cond10-open-P0/P1-defects: TST-0158-D1, TST-0158-D2 (both P1 open)",
   "R3b: manifest_registration.registered=false explicit; SUCCESS-test-row-FAIL (1) + NOT-RUN (4)"
  ],
  "notes": "Live merger appears to have moved on (collision handling likely changed) - recorded evidence is stale; unit cannot be closed against today's tree."
 },
 "TST-0161": {
  "verdict": "FAIL", "receipt_unchanged": True,
  "fail_reasons": [
   "R6: probe1 rc=1 receipt report.conflict.second_conflict.kind != LEASE_CONFLICT",
   "R6: probe2 rc=1 receipt expiry_enforced.commit_a.ok is not false - probes REPRODUCE the receipt's own recorded P1 (expired writer's next write is not fenced)",
   "R2: receipt_core-FAILED-sentinel-with-SUCCESS: sentinel='FAILED:TST-0161 explicit conflicts work, but the expired writer overwrote the successor; condition 11 remains unregistered'",
   "R3b: cond10-open-P0/P1-defect:TST-0161-STALE-WRITER (P1 open)",
   "R3b: manifest_registration.registered=false explicit; SUCCESS-test-row-FAIL (1) + NOT-RUN (1)"
  ],
  "notes": "Both probes rc=1 under native WSL POSIX lane (fcntl available); failures are receipt-vs-live contract drift, not lane artifacts."
 },
 "TST-0162": {
  "verdict": "FAIL", "receipt_unchanged": True,
  "fail_reasons": [
   "R6: probe2 rc=1 FAILED:TST-0162-probe2 honest planner did not redispatch truncated claim - production behavior diverged from the recorded claim",
   "R4-info: supporting-row drift on the production module itself: tools/command-center/claim_resume.py manifest 17859B vs live 2385B (module rewritten post-closure); test-file row also drifted",
   "R5: ENVELOPE-DRIFT (downstream_consumers absent, evidence[4].probes source/verifier pair) - non-gating, recorded"
  ],
  "notes": "probe1 (intact skip / corrupt redispatch) rc=0; R2/R3b clean; the unit fails solely on probe2's live-behavior divergence plus the production-module drift that explains it."
 },
}

closables = json.load(open(OUT / "r2_close_report.json", encoding="utf-8"))
closed = {}
for uid, c in closables.items():
    closed[uid] = {
     "verdict": "CLOSED-PASS", "receipt_unchanged": False,
     "reviewer_id": "independent-reviewer-wave2-shard24-opus-fresh-r2",
     "state": "SUCCESS", "independent": True, "verdict_set": "PASS",
     "new_sha256": c["new_sha256"], "new_bytes": c["new_bytes"],
     "prior_reviewer_preserved_at": "extensions.shard24_prior_reviewer_preserved",
     "prior_reviewer_id": c["prior_reviewer_id"],
     "manifest_primary_row_reregistered": True,
     "post_write_measure": "SUCCESS:delivered",
     "post_write_probes": "native-WSL rc=0 x2" if uid == "TST-0155" else "SUCCESS (program measure re-run)",
     "schema_class": "ENVELOPE-DRIFT", "content_errors": 0,
    }

report = {
 "wave": "2", "shard": "24",
 "reviewer": "independent-reviewer-wave2-shard24-opus-fresh-r2",
 "generated_at": NOW, "units_total": 8, "closed": 4, "failed": 4,
 "method": {
  "schema": "two independent instruments: (1) catalog output_schema full chain via jsonschema Draft2020-12 with manual $ref materialization; (2) program resolver platform/lib/schema_resolver + platform/lib/receipt_schema_gate (C2) + shard-7 ENVELOPE/CONTENT classifier. Both agree: all 8 receipts ENVELOPE-DRIFT, content_errors=0. Envelope drift = schema tightened after legacy closure; recorded not gating (receipt_gate.py policy).",
  "probes": "canonical program measure (_measure_one_delivered.py, g1_python wrapper lane) + raw named-probe lane + native-WSL POSIX lane for fcntl/SIGSTOP probes (0151, 0155, 0161) and for 0155 post-write re-verification. /mnt/c 9P is unfaithful for fs-watch probes (ENODATA/inode churn) - native ext4 copies used.",
  "manifest": "primary row sha256 recomputed CRLF->LF vs live bytes; supporting-row drift censused (production-module drift on 0158/0162 recorded as evidence).",
 },
 "closures": closed,
 "failures": fails,
}
(OUT / "review-report-r2.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("report written; closed=%d failed=%d" % (report["closed"], report["failed"]))
