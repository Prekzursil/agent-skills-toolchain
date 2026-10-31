"""Assemble final review:w3s24 (r2) verdicts from my independently-produced
evidence files, then verify the receipts are STILL byte-unchanged."""
import hashlib
import json
from pathlib import Path

SCRATCH = Path(r"C:/Users/Prekzursil/p2-g1/_reviewer-w3s24-r2")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UIDS = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
        "TST-0223", "TST-0227", "TST-0230", "TST-0233"]

batt = json.loads((SCRATCH / "battery_results.json").read_text(encoding="utf-8"))
pred = json.loads((SCRATCH / "predicate_results_r2.json").read_text(encoding="utf-8"))

FAIL_REASONS = {
    "TST-0206": (
        "receipt INVALID against catalog output_schema receipt.schema.json#/$defs/security_report "
        "(8 schema errors; legacy evidence[2]/evidence[3] rows lack required anchor/confidence/probes "
        "and carry forbidden extra property id) and program 12-condition predicate blocking c4+c6 "
        "(evidence[2]/[3] carry no source probe = undeclared source, no verifier probe, no anchor). "
        "Green sides: artifact parses, probes re-run by this reviewer exit 0 "
        "(probe1_detector_control.py=0, probe2_produced_tree_clean.py=0), manifest primary sha256 "
        "matches live artifact (CRLF-normalized)."
    ),
    "TST-0215": (
        "receipt contradicts its own SUCCESS state on five receipt_core rules at once: sentinel is a "
        "FAILED marker while state=SUCCESS (c5); open P1 defect TST0215-F1 attached (c10) - and the "
        "defect is LIVE-TRUE, this reviewer re-ran probe1_detector_control.py today: "
        "planted_capability_selected=true (planted prose selected by the router), probe2 corpus "
        "differential: refutation_holds_live_injection_steerable=true, 30/30 payloads change routing "
        "and tool sequences; 3 test rows result=FAIL (c7: ROUTING-INVARIANCE, TOOL-SEQUENCE-INVARIANCE, "
        "CONDITION-11); manifest_registration.registered=false (c11); sole downstream consumer "
        "executed=false/read_ok=false (c12); schema-invalid with 7 errors (c4). GREEN sides: artifact "
        "parses, probes exit 0, manifest sha256 matches."
    ),
    "TST-0219": (
        "receipt INVALID against output_schema (14 schema errors; artifacts rows lack bytes/sha256, "
        "non-enum roles resolver-under-test/schema, consumers row lacks probe) and predicate blocking "
        "c3 (min_bytes_threshold absent -> artifact measured against None<2048), c4, c12 "
        "(_measure_one_delivered.py consumer recorded executed=false/read_ok=false, claim only). "
        "Green sides: artifact parses, probes exit 0 (probe1_origin_refusal.py=0, probe2_tree_hash.py=0), "
        "manifest sha256 matches."
    ),
    "TST-0221": (
        "receipt INVALID against output_schema (5 schema errors; consumer row lacks probe) and predicate "
        "blocking c4, c6 (evidence[0] has no verifier probe, evidence[1] has no source probe - the "
        "two-signal requirement is unmet as recorded), c12 (consumer references "
        "probes/TST-0221/UNIT-ARTIFACT-MANIFEST.json which is not in the receipt's artifact set; no raw "
        "probe output recorded). Green sides: artifact parses, probes exit 0 (probe_a_health.py=0, "
        "probe_b_userdata.py=0), manifest sha256 matches."
    ),
    "TST-0223": (
        "receipt INVALID against output_schema (22 schema errors; receipt is missing ENTIRE required "
        "root blocks: schema_version, min_bytes_threshold, negative_controls, downstream_consumers, "
        "manifest_registration, residual_unknowns, report, retry) and predicate blocking c3 (declared "
        "minimum unfalsifiable - threshold absent), c4, c6 (no anchors on evidence), c8 (NO negative "
        "control - the detector is unproven against a known-broken state), c11, c12. Green sides: "
        "artifact parses, probes exit 0 (probe1_property_corpus.py=0, probe2_executor_deep_refusal.py=0), "
        "manifest sha256 matches."
    ),
    "TST-0227": (
        "receipt INVALID against output_schema (9 schema errors; artifacts[0] role 'primary-implementation' "
        "not in enum, evidence method 'filesystem-census' not in enum, negative_controls kind 'both-states' "
        "not in enum, manifest_registration carries forbidden 'derivation') and predicate blocking c4, c12 "
        "(deferred consumer _measure_one_delivered.py executed=false/read_ok=false). Green sides: artifact "
        "parses, probes exit 0 (probe1_both_states.py=0, probe2_concurrent_active.py=0), manifest sha256 "
        "matches."
    ),
    "TST-0230": (
        "receipt INVALID against output_schema (3 schema errors; evidence probe rows missing required "
        "fields) and predicate blocking c4, c6 (evidence[0] and evidence[2] have NO VERIFIER probe - the "
        "second independent signal is absent as recorded). Green sides: artifact parses, probes exit 0 "
        "(probe1_input_counts.py=0, probe2_timing_control.py=0), manifest sha256 matches."
    ),
    "TST-0233": (
        "receipt INVALID against output_schema (23 schema errors; missing report+retry blocks, artifacts[0] "
        "lacks bytes/sha256 and carries extra notes, consumer rows lack probe) and predicate blocking c3 "
        "(min_bytes_threshold absent), c4, c6, c8 (negative control 'complement-more-stages-accepted' did "
        "NOT fire on the bad state - inert detector: the acceptance gate's both-states proof is broken), "
        "c12. Green sides: artifact parses, probes exit 0 (probe1_stage_padded.py=0, "
        "probe2_worse_than_sources.py=0), manifest sha256 matches."
    ),
}

verdicts = {}
for uid in UIDS:
    b = batt[uid]
    p = pred[uid]
    verdicts[uid] = {
        "unit_id": uid,
        "receipt_state": b["state"],
        "receipt_sentinel_head": b["sentinel_head"],
        "reviewer_verdict_in_receipt": b["reviewer_verdict"],
        "reviewer_independent": b["reviewer_independent"],
        "artifact_exists_nonempty_parses": True,
        "not_self_declared_blocked_failed": b["checks"]["not_blocked_failed"] and b["checks"]["no_failure_obj"],
        "probes_rerun_by_this_reviewer_exit0": True,
        "probe_rcs": b["probe_rcs"],
        "probe_inventory_matches_manifest": b["checks"]["probe_inventory_matches_manifest"],
        "manifest_primary_sha256_match_crlf_normalized": True,
        "receipt_sha256_LF": b["receipt_sha256_LF"],
        "schema_error_count_vs_output_schema_fragment": p["schema_error_count"],
        "predicate_blocking_conditions": [f"c{d['n']}:{d['outcome']}" for d in p["blocking_conditions"]],
        "verdict": "FAIL",
        "receipt_bytes_modified_by_reviewer": False,
        "fail_reason": FAIL_REASONS[uid],
        "reviewer": {
            "reviewer_id": "claude-opus-5-5 wf (review:w3s24 r2) fresh-context independent reviewer",
            "independent": True,
            "fresh_context": True,
            "reviewed_at": "2026-10-26",
        },
    }

doc = {
    "shard": "wave 3 shard 24 (review:w3s24, r2 re-run by a fresh independent reviewer; prior _reviewer-w3s24 run REFUTED on its schema-validity fields)",
    "units": UIDS,
    "summary": "0/8 PASS, 8/8 FAIL. Every receipt is schema-INVALID against its catalog-declared output_schema "
               "(receipt_core), i.e. the program's own receipt_validate.py CLI REJECTS all 8 (C2 schema-invalid) and "
               "the 12-condition completion predicate reports c4 UNSATISFIED on all 8. Unit-specific gating failures: "
               "TST-0215 additionally contradicts itself (FAILED sentinel on SUCCESS, live-true open P1 defect, 3 FAIL "
               "test rows, registered=false, dead consumer); TST-0223 is missing entire required receipt blocks and "
               "has NO negative control; TST-0233's negative control is INERT (did not fire on bad state); "
               "TST-0206/0221/0230 evidence lacks the required source+verifier probe pairing; TST-0219/0221/0227/0233 "
               "downstream consumers recorded executed=false/read_ok=false. What DID hold everywhere: artifact "
               "exists/non-empty/parses, NOT self-blocked, both named probes re-run by this reviewer exit 0, manifest "
               "primary sha256 matches the live artifact (CRLF->LF). Receipts left byte-unchanged per FAIL contract.",
    "prior_run_refuted": {
        "prior_dir": "_reviewer-w3s24 (2026-10-26 06:29-06:32)",
        "refuted_claim": "prior verdicts recorded receipt_schema_valid_against_tightened_schema=true and classified "
                         "envelope drift as 'C2-schema-drift-recorded-not-gating' for 7 units, passing them.",
        "evidence": "two mechanically independent signals refute it: (1) this reviewer's gate.validate_receipt "
                    "(fragment-aware) on the CURRENT schema (p2-g1 copy sha256 b258d8c9..., identical bytes to "
                    "ast-integrate physical, file predates the prior run) returns errors on all 8; (2) the program's "
                    "own command-center/receipt_validate.py REJECTs all 8 with 'C2 schema-invalid'; (3) the program's "
                    "own receipt_schema_gate CLI reports c4 UNSATISFIED (schema) on all 8. The prior run's scripts "
                    "contain no schema-validation call - only a resolution check (schema_resolver.resolve) and a "
                    "field-print audit; the schema-valid field was asserted, not executed.",
        "corrective_note": "Program precedent (shard5 review) required ZERO schema errors for PASS and failed a unit "
                           "on a single schema error; this r2 verdicts apply the same fail-closed bar.",
    },
    "receipts_modified": False,
    "verdicts": verdicts,
    "instruments": [
        "_reviewer-w3s24-r2/battery_r2.py (C1-C5 battery; probes executed by this reviewer)",
        "_reviewer-w3s24-r2/predicate_results_r2.json (program gate evaluate_full + fragment schema)",
        "command-center/receipt_validate.py (program admission CLI, third signal)",
        "command-center/p2-wave/probes/<id>/*.raw.txt (live probe outputs re-verified)",
    ],
    "generated": "2026-10-26",
}

dest = SCRATCH / "VERDICTS-w3s24-r2.json"
dest.write_text(json.dumps(doc, indent=1), encoding="utf-8")

# final unchanged proof
for uid in UIDS:
    p = REPO / "command-center" / "receipts" / f"{uid}.json"
    now = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert now == batt[uid]["receipt_sha256_LF"], f"{uid} CHANGED"
print("VERDICTS:", dest)
print("all 8 receipts byte-unchanged: True")
for uid in UIDS:
    print(uid, "| verdict:", verdicts[uid]["verdict"],
          "| schema_err:", verdicts[uid]["schema_error_count_vs_output_schema_fragment"],
          "| blocking:", verdicts[uid]["predicate_blocking_conditions"])
