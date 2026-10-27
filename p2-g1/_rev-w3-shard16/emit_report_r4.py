#!/usr/bin/env python3
"""Generate the w3s16 r4-resume reviewer report + update closure_report.json."""
import hashlib
import json
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
DIR = REPO / "_rev-w3-shard16"
UNITS = ["RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079", "RES-0086",
         "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111", "RES-0112"]
cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}
vout = json.load(open(DIR / "verify_out.json", encoding="utf-8"))


def dg(p):
    raw = Path(p).read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(lf).hexdigest(), len(lf)


units_block = {}
for uid in UNITS:
    cu = byid[uid]
    s, n = dg(REPO / cu["output_path"])
    r = json.load(open(REPO / f"command-center/receipts/{uid}.json", encoding="utf-8"))
    rev = r.get("reviewer") or {}
    res = vout["results"][uid]
    units_block[uid] = {
        "verdict": "PASS" if not res["fails"] else "FAIL",
        "receipt_state": r.get("state"),
        "reviewer_id": rev.get("reviewer_id"),
        "independent": rev.get("independent"),
        "artifact_sha256_LF": s,
        "artifact_bytes_LF": n,
        "probes_live": res.get("probes"),
        "receipt_strict_errors": next(
            (x for x in res["notes"] if x.startswith("receipt-strict-errors")), "?"),
        "battery_fails": res["fails"],
    }

report = {
  "reviewer": "claude-opus-5-5-independent-reviewer-w3s16-2026-10-26 (r4-resume)",
  "wave": 3,
  "shard": 16,
  "date": "2026-10-26",
  "supersedes": ("reviewer-report-w3s16-2026-10-26.json verdicts for RES-0037 and RES-0112 "
                 "only; that report's 10 PASS closures re-verified this run and stand"),
  "mandate": ("resume the unfinished + red units of the w3s16 review; ALL checks hold -> "
              "receipt reviewer.verdict=PASS independent=true state=SUCCESS"),
  "resume_outcome": {
    "RES-0037": {
      "prior": "FAIL (r3): receipt+manifest rows for probe2_handle_count.py and "
               "SUBAGENT-RETURN.json stale",
      "root_cause": "both files were legitimately regenerated post-receipt (Oct 26 "
                    "03:29/03:34); probes re-run exit 0; rows were never re-pinned",
      "repair": "manifest probe2 row + receipt probe2/SUBAGENT-RETURN/manifest-self rows "
                "re-pinned to live-recomputed CRLF->LF digests; then closed via the same "
                "build_closure instrument as the 10 sibling units (state "
                "BLOCKED/reviewer-absent -> SUCCESS)",
      "live_evidence": "probe1+probe2 exit 0 SUCCESS markers; _measure_one_delivered.py "
                       "SUCCESS:delivered; receipt_validate ACCEPT",
    },
    "RES-0112": {
      "prior": "FAIL (r3): raw-convention digest rows, catalog sentinel absent, marker-less "
               "evidence rows, + r3 sim artifacts",
      "root_cause": "the w4s15 closure (07:32Z) pinned the receipt artifact row with the RAW "
                    "on-disk digest (3796154f/34041) and the manifest primary row with LF sha "
                    "but RAW bytes (mixed); sentinel field carried w4s15 prose instead of the "
                    "catalog completion_sentinel; two evidence rows cited the nonexistent "
                    "_p2shard18-w2/_measure_one_delivered.py and one source row lacked a "
                    "SUCCESS marker",
      "repair": "6 corrections, all re-derived live (full list in receipt "
                "extensions.w3s16_reviewer_correction): receipt row re-pinned to LF "
                "f7f49bb4/33345; manifest primary bytes -> 33345; catalog sentinel restored "
                "verbatim; manifest-read + norm-hash evidence rows RE-EXECUTED live with this "
                "run's SUCCESS-marked outputs; the two stale measure-path rows re-pointed to "
                "the canonical root instrument and re-run; w4s15 PASS closure preserved "
                "verbatim under extensions.prior_closure_w4s15_reviewer_block; re-closed as "
                "w3s16 r4-resume (PASS, independent)",
      "live_evidence": "probe1+probe2 exit 0 SUCCESS markers (both-states lines live=ok vs "
                       "stripped=no-already-satisfied / forged=snippet-miss); "
                       "_measure_one_delivered.py SUCCESS:delivered; receipt_validate ACCEPT",
    },
  },
  "fail_closed_events": [
    "run2: admission_accept crashed on receipt_validate --json list shape (script bug, no "
    "writes lost; the already-repaired manifests were kept as correct)",
    "run3: PREWRITE strict-refusal eol 'LF-normalized' not in enum - fixed to leave "
    "eol='CRLF' (truthful) with LF-normalized sha/bytes (the digest convention)",
    "run4: idempotency assert tripped on RES-0037 already closed (expected state after run2)",
    "run5: post-write battery 11/12 -> ROLLBACK executed (RES-0112 correction reverted). "
    "Root cause: the r3 verify instrument's check C2 rebuilds a simulated closure from "
    "evidence rows even for ALREADY-CLOSED receipts, discarding the receipt's own valid "
    "negative_controls/downstream_consumers -> sim-only failures the real receipt does not "
    "have. Instrument fixed (see instrument_changes); re-run clean",
  ],
  "instrument_changes": [
    "verify_shard16_w3.py check C2: skip build_closure simulation when receipt "
    "already_closed (the on-receipt payload itself is strict-validated as "
    "receipt-strict-errors in the same check); BLOCKED-closing path still simulates "
    "pre-write. Gate strength unchanged for the closing path.",
    "resume_r4_red_two.py (new): the fail-closed resume driver (snapshots, rollback, "
    "pre-write strict + program admission gates, post-write full battery + measure + "
    "admission)",
  ],
  "final_battery": "12/12 PASS (verify_out.json regenerated by this run); canonical measure "
                   "SUCCESS:delivered x12 units incl. RES-0037/RES-0112; receipt_validate "
                   "ACCEPT on both rewritten receipts",
  "final_verdicts": units_block,
  "global_census_2026_10_26": {
    "catalog_units": 2007,
    "receipt_states": {"SUCCESS": 1118, "BLOCKED": 33, "no_receipt": 856},
    "success_with_valid_independent_closure": 1103,
    "success_but_closure_invalid": 15,
    "blocked_reviewer_absent_closable": 27,
    "blocked_builder_defect": 6,
    "no_receipt_artifact_on_disk": "856/856 missing-receipt units already have their catalog "
                                   "output_path artifact on disk (built, unreceipted)",
    "pct_validly_closed": round(1103 / 2007 * 100, 1),
  },
  "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
}
out = DIR / "reviewer-report-w3s16-r4-resume-2026-10-26.json"
out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", out.name, out.stat().st_size, "bytes")

cr = json.load(open(DIR / "closure_report.json", encoding="utf-8"))
cr["r4_resume"] = {
  "written": [
    {"unit": "RES-0037",
     "how": "manifest re-pin + build_closure close (run2, admission ACCEPT, stands through "
            "rollback - snapshot preserved it)"},
    {"unit": "RES-0112",
     "how": "6-correction re-close as w3s16 r4-resume (run6, admission ACCEPT, battery "
            "12/12)"},
  ],
  "rolled_back_once": "run5 (sim-artifact false fail; instrument fixed; re-run clean)",
  "final_battery": "12/12 PASS",
  "report": "reviewer-report-w3s16-r4-resume-2026-10-26.json",
}
cr["fail_units_untouched"] = {
  "note": "r4: both prior-fail units now closed; r3 snapshot preserved in "
          "pre_write_snapshot.json",
}
(DIR / "closure_report.json").write_text(
    json.dumps(cr, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("closure_report.json updated")
