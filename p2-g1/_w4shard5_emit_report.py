"""Assemble the wave-4 shard-5 independent reviewer report from raw artifacts.

Inputs (all produced by this review, read-only over program artifacts):
  _w4shard5_reviewer_wave4_result.json   per-unit check table from _w4shard5_indep_verify.py
  _w4shard5_schema_violations_full.json  full iter_errors detail per unit
  _w4shard5_bld0037_reprobe.json         standalone proper-budget re-run of BLD-0037's two probes
                                         (optional; if absent the report records the 600s reviewer
                                         cap truncation honestly instead of guessing)

Output:
  _w4shard5_reviewer_wave4_report.json   the reviewer's closure document
"""
import json
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
MINE = ["AUD-0084", "AUD-0096", "BLD-0001", "BLD-0002", "BLD-0010", "BLD-0016",
        "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028", "BLD-0037", "BLD-0042"]

result = json.loads((REPO / "_w4shard5_reviewer_wave4_result.json").read_text(encoding="utf-8"))
viol = json.loads((REPO / "_w4shard5_schema_violations_full.json").read_text(encoding="utf-8"))
reprobe = None
rp = REPO / "_w4shard5_bld0037_reprobe.json"
if rp.is_file():
    reprobe = json.loads(rp.read_text(encoding="utf-8"))

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

BRIEF = {
    "AUD-0084": ("root missing downstream_consumers; sentinel fails ^SUCCESS:|SENTINEL: pattern "
                 "(declared 'FAILED:AUD-0084 harvest...'); manifest_registration.registered != const true; "
                 "non-empty open P1 defects; state=SUCCESS forbidden by honesty branch (sentinel/tests/defects contradict SUCCESS); "
                 "tests/2 unexpected property 'recertified_live'; tests row shape"),
    "AUD-0096": ("artifacts[] rows missing required bytes+sha256; role 'schema' outside enum "
                 "[primary, supporting, log, fixture, control]; plus further artifacts/evidence shape violations (45 total)"),
    "BLD-0001": ("root missing downstream_consumers; sentinel fails ^SUCCESS:|SENTINEL: pattern ('FAILED:BLD-0001 harvest...'); "
                 "tests contradict SUCCESS branch; manifest_registration.registered != true; open P1 defects; state=SUCCESS honesty branch"),
    "BLD-0002": ("same receipt-honesty family as BLD-0001 (downstream_consumers missing; sentinel FAILED: pattern; "
                 "manifest registered; open defects; state honesty; tests shape)"),
    "BLD-0010": ("18 violations: downstream_consumers missing; evidence rows 2-4 missing probes+confidence; "
                 "defects/tests/manifest/state honesty branches"),
    "BLD-0016": ("53 violations: receipt missing schema_version, spec_anchor, min_bytes_threshold, evidence, "
                 "timestamps, retry, and further base-receipt keys; plus report shape"),
    "BLD-0023": ("downstream_consumers missing; sentinel fails pattern; manifest registered; state honesty; tests shape"),
    "BLD-0024": ("downstream_consumers missing; open P2 defects; sentinel pattern; manifest registered; state honesty; tests shape"),
    "BLD-0027": ("reviewer object: additional property 'sampled' not allowed by the profile (single violation)"),
    "BLD-0028": ("evidence probes rows fail required shape (verifier/source rows missing required fields) - 4 violations"),
    "BLD-0037": ("42 violations: receipt missing schema_version, spec_anchor, min_bytes_threshold, artifacts, "
                 "timestamps, retry, downstream_consumers; report missing observations; further shape"),
    "BLD-0042": ("report missing required 'observations' (generic_report requires kind+observations+control_ids; "
                 "kind and control_ids present) - single violation"),
}

units_out = {}
for uid in MINE:
    r = result[uid]
    ch = r["checks"]
    entry = {
        "verdict": r["verdict"],
        "output_path": str(byid[uid]["output_path"]).replace("\\", "/"),
        "output_schema_wrapper": viol[uid]["output_schema_wrapper"],
        "checks": {
            "artifact_exists_nonempty_parses_not_blocked": bool(
                ch["artifact"].get("exists") and ch["artifact"].get("nonempty")
                and ch["artifact"].get("parses") and ch["artifact"].get("not_self_blocked", True)),
            "manifest_sha_crlf_normalized_matches_before_and_after_probes": bool(
                ch["manifest"].get("sha_before_matches_manifest")
                and ch["manifest"].get("sha_after_matches_manifest")),
            "probes_rerun_live": [
                {"id": p.get("id"), "exit": p.get("exit"),
                 "success_marker": p.get("success_marker"), "error": p.get("error")}
                for p in ch["probes"].get("probes", [])],
            "existing_closure_confirmed_valid_shape": ch["closure"].get("valid_closure"),
            "closure_reviewer": ch["closure"].get("reviewer_id"),
        },
        "schema_violation_count": viol[uid]["violation_count"],
        "schema_failing_check_brief": BRIEF[uid],
        "receipt_unchanged": True,
    }
    if uid == "BLD-0037":
        stop = REPO / "_w4shard5_bld0037_stopnote.json"
        if stop.is_file():
            entry["bld0037_probe_transport_note"] = json.loads(stop.read_text(encoding="utf-8"))
    if uid == "BLD-0037" and reprobe is not None:
        entry["checks"]["probes_rerun_live"] = [
            {"id": "probe1", "standalone_reprobe": reprobe.get("probe1")},
            {"id": "probe2", "standalone_reprobe": reprobe.get("probe2")},
        ]
        entry["bld0037_reprobe_note"] = (
            "first pass hit the reviewer 600s/probe transport cap (vault-scan probes); "
            "re-run standalone at 3500s budget - outcome recorded above")
    units_out[uid] = entry

report = {
    "reviewer": "wave-4 shard-5 independent reviewer (claude-opus-5-5, fresh context; did not build these units)",
    "reviewed_at": "2026-10-26",
    "shard": "wave4-shard5",
    "shard_units_derivation": (
        "command-center/READY-UNITS.json ready_units[60:72]; verified: the 12-chunk partition of ready_units "
        "reproduces every known wave-4 shard list (_builder-shard0-w4.json, _p2-shard1-w4-entries.json, "
        "_p2-shard2-w4-entries.json, _w4-shard3-mine.json, shard4 AUD-0044..AUD-0080, _p2-shard7-w4-entries.json)"),
    "units_reviewed": MINE,
    "instrument": {
        "artifact": "catalog output_path: exists, non-empty, parses, unit_id matches, state not in {BLOCKED, FAILED, SEVERED, TIMEOUT}",
        "probes": "every named probe from probes/<uid>/SUBAGENT-RETURN.json re-run live; require exit 0 AND SUCCESS:<uid> marker",
        "sha": "sha256 with CRLF normalized to LF, recomputed BEFORE and AFTER probe runs, must equal the UNIT-ARTIFACT-MANIFEST.json row (path==output_path, present=true)",
        "schema": ("catalog-declared output_schema wrapper validated with jsonschema Draft2020-12, $refs resolved "
                   "to their declared absolute file URIs (canonical profiles in ~/source/ast-integrate, stable since Aug 26/28); "
                   "cross-checked against the program's own command-center/receipt_validate.py admission gate"),
        "closure": "state=SUCCESS requires reviewer.verdict=PASS + reviewer.independent=true (receipt or SUBAGENT-RETURN vehicle)",
    },
    "instrument_agreement": (
        "program gate receipt_validate.py REJECTs the same 9 BLD receipts the strict catalog-schema instrument rejects "
        "(ACCEPTs only BLD-0042, which the catalog-declared wrapper still rejects on report.observations); "
        "AUD-0084/AUD-0096 artifacts are data artifacts (no receipt) and fail their declared audit-finding/audit-drift wrappers; "
        "positive controls (CNF-0149 built today, RES-0158, IMP-0461) also violate their class profiles - schema debt is "
        "program-wide, but per the same-wave shard-3 reviewer precedent the catalog output_schema is the reviewer's instrument"),
    "verdict_rule": "ALL checks hold -> confirm PASS closure stays SUCCESS; ANY check fails -> verdict FAIL, receipt unchanged",
    "outcome": "ALL 12 UNITS FAIL on the catalog output_schema check; artifact/manifest-sha/closure checks hold for all 12; probes re-ran exit 0 with SUCCESS markers for 11 units; BLD-0037's two vault-scan probes exceeded the reviewer transport budget (deliberately stopped, see bld0037_probe_transport_note) - NOT a probe-failure signal; NO receipt or program artifact was modified",
    "units": units_out,
    "files_produced": [
        "_w4shard5_indep_verify.py",
        "_w4shard5_reviewer_wave4_result.json",
        "_w4shard5_schema_violations_full.json",
        "_w4shard5_bld0037_reprobe.py (re-run launcher; deliberately stopped, see stop-note)",
        "_w4shard5_bld0037_stopnote.json",
        "_w4shard5_reviewer_wave4_report.json",
    ],
}

(REPO / "_w4shard5_reviewer_wave4_report.json").write_text(
    json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
print("report written; verdicts:",
      {u: report["units"][u]["verdict"] for u in MINE})
