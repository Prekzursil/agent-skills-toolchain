"""Assemble review:w3s24 (r3) final verdicts from MY independently-produced
battery evidence, then prove the receipts are STILL byte-unchanged (FAIL
contract: receipts are never modified by the reviewer)."""
import hashlib
import json
from pathlib import Path

SCRATCH = Path(r"C:/Users/Prekzursil/p2-g1/_reviewer-w3s24-r3")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UIDS = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
        "TST-0223", "TST-0227", "TST-0230", "TST-0233"]

FAIL_REASONS = {
    "TST-0206": (
        "receipt INVALID against its catalog output_schema (command-center/schema/receipt.schema.json"
        "#/$defs/security_report; 8 schema errors, IDENTICAL count under the physical platform copy - "
        "the catalog chain delegates to the same def - and program CLI receipt_validate.py also REJECTs): "
        "legacy evidence[2]/evidence[3] rows lack required anchor/confidence/probes and carry forbidden "
        "extra property id. Program 12-condition predicate (disk-verified this run, stronger than the r2 "
        "run that left c2/c3 NOT-CHECKED): c3 declared bytes 14200 != on-disk 32429 for the receipt "
        "artifact; c4 schema-invalid; c6 evidence[2]/[3] have no source probe (undeclared source = zero "
        "signals), no verifier probe, no anchor. GREEN sides (all re-derived by this reviewer): artifact "
        "parses; state=SUCCESS no failure object; both named probes re-run exit 0 "
        "(probe1_detector_control.py=0, probe2_produced_tree_clean.py=0); probe inventory matches "
        "manifest; manifest primary sha256 matches live artifact CRLF->LF."
    ),
    "TST-0215": (
        "receipt contradicts its own SUCCESS state and carries a LIVE-TRUE open P1: sentinel is a "
        "FAILED marker ('FAILED:TST-0215 fresh re...') while state=SUCCESS (c5); open P1 TST0215-F1 "
        "(c10) is live-true - this reviewer re-ran both probes TODAY: probe1_detector_control.py "
        "reports planted_capability_selected=true; probe2_corpus_differential.py reports "
        "target_planted_selected_count=30 / target_case_changed_count=30 of 30 payloads (injection "
        "steers routing and tool sequences); 3 test rows FAIL (c7: TST0215-ROUTING-INVARIANCE, "
        "TOOL-SEQUENCE-INVARIANCE, CONDITION-11); manifest_registration.registered=false (c11); sole "
        "consumer executed=false/read_ok=false (c12); schema INVALID vs output_schema security_report "
        "(7 errors, both instruments + CLI agree); c3 declared 466184 != on-disk 470773. GREEN sides: "
        "artifact parses; both probes exit 0; manifest primary sha256 matches."
    ),
    "TST-0219": (
        "receipt INVALID against output_schema (14 schema errors, cc-chain == platform copy; CLI "
        "REJECTs with 13): artifacts rows lack required bytes/sha256, roles resolver-under-test/schema "
        "not in enum, consumers row lacks probe. Predicate: c3 min_bytes_threshold absent - 'meaningful "
        "minimum' unfalsifiable (None<2048); c4 schema-invalid; c12 downstream consumer "
        "command-center/p2-wave/_measure_one_delivered.py recorded executed=false/read_ok=false (claim "
        "only). GREEN sides: artifact parses; both probes re-run exit 0 (probe1_origin_refusal.py=0, "
        "probe2_tree_hash.py=0); manifest primary sha256 matches CRLF->LF."
    ),
    "TST-0221": (
        "receipt INVALID against output_schema (5 schema errors, both instruments + CLI agree): "
        "downstream_consumers/0 lacks required probe field. Predicate: c3 declared 26543 != on-disk "
        "35596; c4; c6 evidence[0] has no verifier probe and evidence[1] has no source probe - the "
        "source+verifier pair requirement is unmet as recorded; c12 consumer references "
        "probes/TST-0221/UNIT-ARTIFACT-MANIFEST.json which is not in this receipt's artifact set and no "
        "raw probe output is recorded. GREEN sides: artifact parses; probes probe_a_health.py=0, "
        "probe_b_userdata.py=0 re-run by this reviewer; manifest primary sha256 matches."
    ),
    "TST-0223": (
        "receipt INVALID against output_schema (22 schema errors, both instruments + CLI agree): "
        "missing ENTIRE required root blocks - downstream_consumers, manifest_registration, report, "
        "retry, negative_controls, schema_version, min_bytes_threshold, residual_unknowns. Predicate: "
        "c3 threshold absent (declared minimum unfalsifiable); c4; c6 evidence[0]/[1] carry no anchor; "
        "c8 NO negative control at all - detector unproven against a known-broken state; c11 no "
        "manifest_registration block; c12 no downstream consumer probe. GREEN sides: artifact parses; "
        "both probes re-run exit 0 (probe1_property_corpus.py=0, probe2_executor_deep_refusal.py=0); "
        "manifest primary sha256 matches."
    ),
    "TST-0227": (
        "receipt INVALID against output_schema (9 schema errors, both instruments + CLI agree): "
        "artifacts[0] role 'primary-implementation' not in enum, evidence method 'filesystem-census' "
        "not in enum, negative_controls kind 'both-states' not in enum, missing report block. "
        "Predicate: c3 declared sizes/sha256 DISAGREE WITH DISK (tools/lib/workspace.py declared 11571 "
        "vs on-disk 10477; test file likewise) - first surfaced by this r3 run's disk-verified "
        "predicate; c4; c12 consumer _measure_one_delivered.py executed=false/read_ok=false. GREEN "
        "sides: artifact parses; both probes re-run exit 0 (probe1_both_states.py=0, "
        "probe2_concurrent_active.py=0); manifest primary sha256 matches."
    ),
    "TST-0230": (
        "receipt INVALID against output_schema (3 schema errors, both instruments + CLI agree): "
        "evidence probe rows missing required fields. Predicate: c3 declared 33241 != on-disk 40593 "
        "(disk-verified this run); c4; c6 evidence[0] and evidence[2] have NO VERIFIER probe - second "
        "independent signal absent as recorded. GREEN sides: artifact parses; both probes re-run exit 0 "
        "(probe1_input_counts.py=0, probe2_timing_control.py=0); manifest primary sha256 matches."
    ),
    "TST-0233": (
        "receipt INVALID against output_schema (23 schema errors, both instruments + CLI agree): "
        "missing report+retry root blocks, artifacts[0] lacks bytes/sha256 and carries extra notes, "
        "consumer rows lack probe. Predicate: c3 min_bytes_threshold absent; c4; c6 evidence[0] no "
        "verifier probe, evidence[1] no source probe; c8 program gate reports control "
        "'complement-more-stages-accepted' did not fire on bad state (the program's own c8 rule "
        "requires every recorded control fired_on_bad_state=true); c12 consumer "
        "_measure_one_delivered.py not executed (claim only). GREEN sides: artifact parses; both probes "
        "re-run exit 0 (probe1_stage_padded.py=0, probe2_worse_than_sources.py=0); manifest primary "
        "sha256 matches."
    ),
}

batt = json.loads((SCRATCH / "battery_results.json").read_text(encoding="utf-8"))
U = batt["units"]

results: dict[str, dict] = {}
for uid in UIDS:
    b = U[uid]
    verdict = b["verdict"]
    blocking = [f"c{x['n']}:{x['outcome']}" for x in b.get("predicate_blocking", [])]
    results[uid] = {
        "unit_id": uid,
        "receipt_state": b.get("state"),
        "receipt_sentinel_head": b.get("sentinel_head"),
        "reviewer_verdict_in_receipt": b.get("reviewer_verdict"),
        "reviewer_independent": b.get("reviewer_independent"),
        "artifact_exists_nonempty_parses": bool(
            b["checks"].get("artifact_exists_nonempty") and b["checks"].get("artifact_parses")
        ),
        "not_self_declared_blocked_failed": bool(
            b["checks"].get("not_blocked_failed") and b["checks"].get("no_failure_obj")
        ),
        "probes_rerun_by_this_reviewer_exit0": bool(b["checks"].get("probes_all_exit0")),
        "probe_rcs": b.get("probe_rcs"),
        "probe_inventory_matches_manifest": bool(b["checks"].get("probe_inventory_matches_manifest")),
        "manifest_primary_sha256_match_crlf_normalized": bool(b["checks"].get("manifest_primary_sha_match")),
        "receipt_sha256_LF": b.get("receipt_sha256_LF"),
        "schema_error_count_vs_catalog_declared_chain": b.get("schema_error_count_cc_chain"),
        "schema_error_count_vs_platform_copy": b.get("schema_error_count_platform_copy"),
        "schema_instruments_agree": b.get("schema_instruments_agree"),
        "program_cli_admission": "REJECT (C2 schema-invalid)" if verdict == "FAIL" else "ACCEPT",
        "predicate_complete": b.get("predicate_complete"),
        "predicate_marker": b.get("predicate_marker"),
        "predicate_blocking_conditions": blocking,
        "verdict": verdict,
        "receipt_bytes_modified_by_reviewer": False,
        "fail_reason": FAIL_REASONS[uid] if verdict == "FAIL" else None,
        "reviewer": {
            "reviewer_id": "claude-opus-5-5 wf (review:w3s24 r3) fresh-context independent reviewer",
            "independent": True,
            "fresh_context": True,
            "reviewed_at": "2026-10-26",
        },
    }

doc = {
    "shard": "wave 3 shard 24 (review:w3s24, r3 re-run by a fresh independent reviewer; "
             "r1 refuted on asserted-not-executed schema fields; r2 failed 8/8; r3 re-derived ALL "
             "evidence fresh with a STRONGER predicate: disk-verified c2/c3)",
    "units": UIDS,
    "summary": "0/8 PASS, 8/8 FAIL (fresh re-derivation, not inherited from r2). Receipts were "
               "byte-unchanged since r2 (sha256 + mtime check), so the underlying defects persist. "
               "ALL 8 receipts are schema-INVALID against their catalog output_schema - verified via "
               "TWO instruments that agree exactly (catalog-declared command-center chain 8/7/14/5/"
               "22/9/3/23 errors; physical platform copy identical counts) plus the program's own "
               "receipt_validate.py CLI which REJECTs all 8. ALL 8 fail the disk-verified 12-condition "
               "predicate (c4 everywhere; c3 additionally on 6 units: declared bytes/sha256 disagree "
               "with disk on TST-0206/0215/0221/0227/0230, threshold absent on TST-0219/0223/0233). "
               "TST-0215 alone fails 8 conditions: FAILED sentinel on SUCCESS, live-true open P1 "
               "(re-proven live this run: planted_capability_selected=true, 30/30 corpus payloads "
               "change routing), 3 FAIL test rows, registered=false, dead consumer. TST-0223 has NO "
               "negative control and missing root blocks. GREEN sides held everywhere: artifact "
               "exists/non-empty/parses, not self-blocked, all 16 named probes re-run by this "
               "reviewer exit 0, probe inventory matches manifests, manifest primary sha256 matches "
               "live artifacts CRLF->LF. Receipts left byte-unchanged per FAIL contract.",
    "schema_topology_note": "catalog output_schema names command-center/schema/receipt.schema.json "
                            "whose $defs delegate (pure allOf $ref, no extra constraints) through "
                            "platform/schema/artifact-class-profiles.schema.json to the physical "
                            "defs in platform/schema/receipt.schema.json - both trees byte-identical "
                            "(p2-g1 == source/ast-integrate, asserted in battery precondition); "
                            "validating via either path yields identical error sets.",
    "prior_runs": {
        "r1 (_reviewer-w3s24)": "REFUTED (r2): schema-valid fields asserted, never executed",
        "r2 (_reviewer-w3s24-r2)": "8/8 FAIL; receipts unchanged since; r3 confirms on fresh evidence",
    },
    "receipts_modified": False,
    "verdicts": results,
    "instruments": [
        "_reviewer-w3s24-r3/battery_r3.py (C1-C5 + disk-verified 12-condition predicate; 16 probes "
        "executed by this reviewer)",
        "catalog-declared schema chain via explicit 3-file referencing Registry (CC -> profiles -> "
        "platform), plus physical platform copy for equivalence",
        "command-center/receipt_validate.py CLI (program admission, third signal; REJECTs all 8)",
        "receipt sha256 + mtime proof that receipts are byte-unchanged since the r2 run",
    ],
    "generated": "2026-10-26",
}
dest = SCRATCH / "VERDICTS-w3s24-r3.json"
dest.write_text(json.dumps(doc, indent=1), encoding="utf-8")

# final unchanged proof
for uid in UIDS:
    p = REPO / "command-center" / "receipts" / f"{uid}.json"
    now = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert now == U[uid]["receipt_sha256_LF"], f"{uid} CHANGED"
print("VERDICTS:", dest)
print("all 8 receipts byte-unchanged: True")
for uid in UIDS:
    v = results[uid]
    print(uid, "| verdict:", v["verdict"],
          "| schema_err(cc=platform):", v["schema_error_count_vs_catalog_declared_chain"],
          "| blocking:", ",".join(v["predicate_blocking_conditions"]))
