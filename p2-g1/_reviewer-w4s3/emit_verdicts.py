#!/usr/bin/env python3
"""w4s3 reviewer phase 3: emit verdicts.json + REVIEW-RETURN.json.

Contract applied: ANY failing check -> verdict FAIL with the precise failing
check, receipt UNCHANGED. Zero units closed by this shard; this file writes
only into _reviewer-w4s3/.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
IDS = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
       "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]

sweep = json.loads((HERE / "sweep.json").read_text(encoding="utf-8"))
full = json.loads((HERE / "schema_full.json").read_text(encoding="utf-8"))
probes = json.loads((HERE / "probe_results.json").read_text(encoding="utf-8"))
canon = json.loads((HERE / "canonical_resolver_results.json").read_text(encoding="utf-8"))

# manual probe corrections recorded by the reviewer (full-env re-runs + AUD-0008 battery fix)
PROBE_NOTES = {
    "AUD-0008": "battery placeholder row rc=2 (command-center/wave4_audit8_probe.py does not exist) superseded by a direct full-env re-run: probe1_ancestor.py rc=0 (SUCCESS:AUD-0008-probe1 ancestor invariant re-proven; catalog recount 2007 matches), probe2_path_surface.py rc=0 (SUCCESS:AUD-0008-probe2 path classifier re-derived), _measure_one_delivered.py rc=0 (SUCCESS:delivered AUD-0008, bytes=9770 sha256=6e331ae6...)",
    "AUD-0033": "first battery run rc=1 on all three commands was a RUNNER ARTIFACT (stripped env broke Path.home() in common.py:60), not a unit defect; full-env re-run: probe1_extract_existence.py rc=0, probe2_git_log_missing.py rc=0 (probe handles the non-git worktree as classification=GIT-UNAVAILABLE honestly), _measure_one_delivered.py rc=0 SUCCESS:delivered AUD-0033",
}

REVIEWER_REQUIREMENT = {
    "AUD-0008": "one cross-vendor Codex reviewer who re-runs ONLY the second probe",
    "AUD-0026": "one cross-vendor Codex reviewer who re-runs ONLY the second probe",
    "AUD-0032": "one cross-vendor Codex reviewer who re-runs ONLY the second probe",
    "AUD-0042": "one cross-vendor Codex reviewer who re-runs ONLY the second probe",
}

def err_classes(errs: list[str]) -> list[str]:
    out = []
    for e in errs:
        head = e.split(": ", 1)[-1]
        cls = head.split("'")[0].strip() if head.startswith("'") else head.split()[0]
        label = None
        if "is a required property" in head:
            label = "missing-required:" + head.split("'")[1]
        elif "is not one of" in head:
            label = "enum-violation"
        elif "Additional properties" in head:
            label = "additional-properties:" + ",".join(x.strip() for x in head.split("(")[1].split(")")[0].split(",")) if "(" in head else "additional-properties"
        elif "should not be valid under" in head:
            label = "const-violation:" + head.split("'")[1] if "'" in head else "const-violation"
        elif "is not of type" in head:
            label = "type-violation:" + head.split("'")[1] if "'" in head else "type-violation"
        else:
            label = "other:" + head[:60]
        if label not in out:
            out.append(label)
    return out[:10]

per_unit = {}
for uid in IDS:
    sw, sf = sweep[uid], full[uid]
    pr = probes.get(uid, {})
    rc_codes = {c.split("/")[-1]: d["exit_code"] for c, d in pr.items()}
    schema_errors = sf["instrumentB_errors"]
    eclasses = err_classes(schema_errors)
    succ = sw["success_preconditions"]
    # receipt-side SUCCESS preconditions that would ALSO block a future closure
    missing_for_success = []
    if not succ["tests_all_pass"]:
        missing_for_success.append(f"tests present-and-all-PASS (now {succ['tests_count']} rows)")
    if not succ["negative_controls_valid"]:
        missing_for_success.append(f"negative_controls >=1 valid (now {succ['negative_controls_count']})")
    if not succ["residual_unknowns_present"]:
        missing_for_success.append("residual_unknowns block absent")
    if not succ["downstream_consumers_valid"]:
        missing_for_success.append(f"downstream_consumers >=1 executed+read_ok with raw probe output (now {succ['downstream_consumers_count']})")
    verdict = "FAIL"
    detail = (
        f"artifact at {sw['output_path']} exists ({sw['artifact_bytes']} B), parses, not self-blocked, "
        f"manifest primary sha256 row matches live CRLF->LF sha {sw['live_sha_lf'][:12]}..., "
        f"all named probes exit 0; BUT output_schema FAILS under all three instruments: "
        f"A shim-as-declared={sf['error_count_A']}, B local-fragment={sf['error_count_B']}, "
        f"C program schema_resolver.validate_artifact (AST_INTEGRATE_ROOT=p2-g1)={canon[uid]['error_count']}. "
        f"schema vs {sf['output_schema']} ({sf['physical_fragment']} fragment); "
        f"classes: {', '.join(eclasses[:6])}."
    )
    per_unit[uid] = {
        "verdict": verdict,
        "failing_check": "output_schema",
        "schema_errors": len(schema_errors),
        "schema_error_classes": eclasses,
        "probe_exit_codes": rc_codes,
        "probe_note": PROBE_NOTES.get(uid),
        "detail": detail,
        "checks_holding": {
            "artifact_exists_nonempty_parses_not_self_blocked": True,
            "artifact_bytes": sw["artifact_bytes"],
            "manifest_sha256_lf_match": sw["manifest_sha_match_lf"],
            "live_sha256_lf": sw["live_sha_lf"],
            "probes_all_exit_0": True,
            "receipt_admission_ACCEPT": sw["receipt_schema_errors_now"] == 0,
            "receipt_artifact_rows_match_disk": succ["artifacts_rows_bytes_match_disk"],
        },
        "receipt_success_preconditions_missing": missing_for_success,
        "codex_reviewer_required_at_closure": REVIEWER_REQUIREMENT.get(uid),
    }

receipts_unchanged = {}
for uid in IDS:
    p = REPO / "command-center/receipts" / f"{uid}.json"
    receipts_unchanged[uid] = hashlib.sha256(p.read_bytes()).hexdigest()

doc = {
    "reviewer": "review:w4s3 (wave 4 shard 3 independent reviewer, Opus 5.5 claude-opus-5-5, 2026-10-26)",
    "assignment_derivation": "partition:w4 assignments extracted from _reviewer-w4s8/build-assignments-all-waves.json key 'build:w4s3' (12 ids, verbatim); review shard N reviews build shard N's list (proven by sibling closures recorded in _reviewer-w4s23/verdicts.json). review:w4s3 == build:w4s3 list.",
    "units": IDS,
    "per_unit": per_unit,
    "checks_holding": [
        "catalog entry present for all 12 ids (command-center/WORK-UNIT-CATALOG.json work_units)",
        "artifact at catalog output_path exists, non-empty, parses as JSON, not self-declared BLOCKED/FAILED for all 12",
        "all named probe scripts re-run by this reviewer exit 0 for all 12 incl. command-center/p2-wave/_measure_one_delivered.py -> SUCCESS:delivered <id> (evidence: _reviewer-w4s3/probe_results.json + probe_run.log; two runner artifacts corrected and documented per-unit)",
        "probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary sha256 row matches the live artifact CRLF->LF-normalized for all 12 (evidence: _reviewer-w4s3/sweep.json)",
        "all 12 receipts ADMITTED by the program's own admission validator (command-center/receipt_validate.py: C1 parses, C2 schema-valid, C3 in catalog, C4 sentinel binds)",
        "receipt artifacts[] rows match disk bytes and primary sha256 for all 12",
        "no receipt mutated by this review (FAIL verdicts -> receipts untouched per contract); receipt sha256 ledger in receipts_unchanged.json",
    ],
    "failing_check_detail": {
        "instrument": "jsonschema Draft2020-12 against the catalog-declared output_schema shim, resolved through its absolute file:// $ref",
        "second_instrument": "the SAME validation against the LOCAL physical profile platform/schema/artifact-class-profiles.schema.json#/$defs/<class> fragment directly (no remote retrieval) - identical error counts and verdicts for all 12 (evidence: _reviewer-w4s3/schema_full.json); the shim's $ref target in ~/source/ast-integrate is byte-identical (LF sha f89a4209d2fbb013...) to the local profile, so resolution path does not change the verdict (w4s23 precedent re-verified)",
        "third_instrument_program_canonical": "platform/lib/schema_resolver.py::validate_artifact with AST_INTEGRATE_ROOT=p2-g1 (the exact instrument sibling w4s10 used) - same verdict for all 12 (evidence: _reviewer-w4s3/canonical_resolver_results.json); per-unit error counts A/B/C: " + ", ".join(f"{uid}={full[uid]['error_count_A']}/{full[uid]['error_count_B']}/{canon[uid]['error_count']}" for uid in IDS),
        "result": "REJECT for 12 of 12 artifacts (1-49 errors each)",
        "error_classes": [
            "artifacts[] rows missing bytes/sha256/exists (ARC-0055/0056/0076, AUD-0005, AUD-0043)",
            "artifacts[].role custom strings ('named-probe', 'schema', 'detector', ...) vs [primary, supporting, log, fixture, control]",
            "artifacts[] rows carrying unexpected keys present/receipt_path/unit_id (AUD-0026)",
            "evidence[] items missing probes[]/verdict or carrying unexpected keys instrument/detail/kind (AUD-0008, AUD-0042); probe rows violating the probe schema method enum (AUD-0003)",
            "manifest_registration unexpected keys global_catalog_write/derivation (AUD-0003, AUD-0026, AUD-0032)",
            "AUD-0010: artifact self-contradicts - state=SUCCESS with a FAILED: sentinel and an OPEN P1 defect (AUD-0010-D4, private origin Prekzursil/databricks-fanout-harness unmeasurable on the worker; 5/6 origins within 2%)",
            "AUD-0033: a tests[] row result not PASS (AUD-0033-detector-control-required-fixture)",
            "failure: null not of type object (AUD-0003)",
        ],
        "full_error_lists": "_reviewer-w4s3/schema_full.json",
    },
    "receipt_closure_integrity_finding": "ALL 12 receipts lack residual_unknowns, and 6 lack any negative_controls row (ARC-0055, ARC-0056, AUD-0003, AUD-0005, AUD-0010, AUD-0043); AUD-0043 additionally has 0 tests rows and 0 downstream_consumers. receipt_core's SUCCESS-conditional allOf requires ALL of tests(all-PASS)/negative_controls/residual_unknowns/downstream_consumers once state=SUCCESS, so a reviewer flip of state+reviewer alone would make every one of these receipts C2 schema-invalid at closure. Builder-side completion fields are required BEFORE any closure; the reviewer will not fabricate them.",
    "receipt_action": "NONE - receipts left byte-unchanged per contract (any FAIL verdict -> receipt untouched)",
    "honesty_note": "partial green reported as partial: artifact predicate, probe re-runs, manifest sha registration and receipt admission all hold for 12/12; the schema check fails 12/12, so zero units closed by this shard.",
    "remediation_note": "per unit: (1) reshape the artifact at output_path to its artifact-class profile (fill artifacts[] bytes/sha256/enum role rows, evidence[] probes/verdict, manifest_registration without extra keys, fix the AUD-0033 fixture-control test row, resolve AUD-0010's SUCCESS+FAILED-sentinel+open-P1 self-contradiction); because the artifact at output_path is NOT the receipt and no manifest row registers the receipt file, artifact rewrites invalidate ONLY the artifact's own manifest sha row - rewrite artifact + manifest row together; (2) add the receipt-side SUCCESS fields (residual_unknowns; negative_controls where absent; for AUD-0043 also tests + downstream_consumers); (3) for AUD-0008/0026/0032/0042 the catalog names a cross-vendor Codex reviewer who re-runs probe2 - schedule that at closure time; (4) resubmit; a fresh independent reviewer PASS then closes.",
    "census_at_review": {"units": 2007, "delivered_static": 453, "receipts_present": 1166, "reviewer_closed_green": 1099, "source": "_w4s2_full2007_census.py re-run 2026-10-26 21:51 (numbers byte-identical to the builder's snapshot; the re-run overwrote _w4s2_full2007_census_out.json in place with identical content - deterministic script, disclosed)"},
}

(HERE / "verdicts.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
(HERE / "receipts_unchanged.json").write_text(json.dumps(receipts_unchanged, indent=1), encoding="utf-8")
print("wrote verdicts.json + receipts_unchanged.json")
for uid in IDS:
    print(uid, per_unit[uid]["verdict"], "| schema_errors:", per_unit[uid]["schema_errors"])
