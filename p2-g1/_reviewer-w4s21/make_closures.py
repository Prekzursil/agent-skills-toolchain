import json
from pathlib import Path
from datetime import datetime, timezone

bat = json.load(open('_reviewer-w4s21/battery-out-after-probes.json', encoding='utf-8'))

probe_runs = {
 "TST-0206": {"probe1_detector_control.py": 0, "probe2_produced_tree_clean.py": 0},
 "TST-0215": {"probe1_detector_control.py": 0, "probe2_corpus_differential.py": 0},
 "TST-0219": {"probe1_origin_refusal.py": 0, "probe2_tree_hash.py": 0},
 "TST-0221": {"probe_a_health.py": 0, "probe_b_userdata.py": 0},
 "TST-0223": {"probe1_property_corpus.py": 0, "probe2_executor_deep_refusal.py": 0},
 "TST-0227": {"probe1_both_states.py": 0, "probe2_concurrent_active.py": 0},
 "TST-0230": {"probe1_input_counts.py": 0, "probe2_timing_control.py": 0},
 "TST-0233": {"probe1_stage_padded.py": 0, "probe2_worse_than_sources.py": 0},
 "TST-0236": {"probe1_three_outcomes.py": 0, "probe2_independent_rehash.py": 0},
 "TST-0238": {"probe1_shim_detector.py": 0, "probe2_cancel_and_trace.py": 0},
 "TST-0243": {"probe1_mechanical_join.py": 0, "probe2_short_timeout_control.py": 0},
 "TST-0245": {"probe1_nocolor_vs_stripped_sgr.py": 0, "probe2_token_enumeration.py": 0},
}

extra_fail = {
 "TST-0215": [
  "not_self_declared_BLOCKED_or_FAILED: sentinel FAILED:TST-0215 over state=SUCCESS",
  "content_vs_closure: body records REFUTED target (target_pass=false, changed_route_count=30/30, changed_tool_sequence_count=30/30, reviewer_gate 0/2, condition11_live_green=false); defects TST0215-F1 P1 + TST0215-F2 P2 open; SUCCESS envelope is a false closure",
  "receipt_output_schema_field_matches_catalog: receipt has NO output_schema field",
 ],
 "TST-0221": ["receipt_output_schema_field_matches_catalog: differs from catalog"],
 "TST-0227": ["receipt_output_schema_field_matches_catalog: differs from catalog"],
 "TST-0230": ["receipt_output_schema_field_matches_catalog: differs from catalog"],
 "TST-0236": ["receipt_output_schema_field_matches_catalog: differs from catalog"],
 "TST-0245": ["receipt_output_schema_field_matches_catalog: differs from catalog"],
}

schema_note = {
 "TST-0206": "security_report: evidence/2 lacks required anchor/confidence/probes + disallowed props (8 errs)",
 "TST-0215": "security_report: defects[] rows violate defect schema (7 errs)",
 "TST-0219": "security_report: artifacts rows missing bytes/sha256; role resolver-under-test not in enum (14 errs)",
 "TST-0221": "security_report: downstream_consumers/0 missing probe; evidence probe rows invalid (5 errs)",
 "TST-0223": "security_report: root required props missing (downstream_consumers, manifest_registration, ...) (22 errs)",
 "TST-0227": "security_report: root report missing; role primary-implementation not in enum (9 errs)",
 "TST-0230": "benchmark_result: evidence probe rows violate probe-item schema (3 errs)",
 "TST-0233": "benchmark_result: root report+retry missing; artifacts missing bytes/sha256 (23 errs)",
 "TST-0236": "benchmark_result: root report missing; artifacts carry manifest-only keys (19 errs)",
 "TST-0238": "benchmark_result: root downstream_consumers+report missing; artifacts missing bytes/sha256 (29 errs)",
 "TST-0243": "benchmark_result: artifacts/0 missing bytes/sha256; manifest_registration disallowed derivation (3 errs)",
 "TST-0245": "ux_report: root report missing; artifacts carry manifest-only keys (23 errs)",
}

units = {}
for uid, r in bat.items():
    units[uid] = {
        "verdict": "FAIL",
        "failing_check": "output_schema_valid",
        "additional_failing_checks": extra_fail.get(uid, []),
        "schema_detail": schema_note[uid],
        "schema_errors_transport1": r.get("t1_error_count"),
        "schema_errors_transport2": r.get("t2_error_count"),
        "first_transport1_error": (r.get("t1_errors") or [None])[0],
        "checks_holding": {
            "catalog_entry_present": r.get("catalog_present"),
            "artifact_exists_nonempty_parses": bool(r.get("exists") and r.get("nonempty") and r.get("parses")),
            "state_not_BLOCKED_FAILED": not r.get("self_declared_failed"),
            "manifest_primary_sha_match_crlf_normalized": r.get("sha_match"),
            "manifest_primary_bytes_match": r.get("bytes_match"),
            "manifest_path_matches_catalog_output_path": r.get("manifest_path_matches_catalog"),
            "nonprimary_manifest_rows_all_match": not r.get("nonprimary_row_mismatches"),
            "live_probes_exit0": probe_runs[uid],
        },
        "receipt_action": "unchanged (verdict FAIL; builder must repair the receipt and re-submit for review)",
    }

out = {
 "reviewer": "wave-4-shard-21-independent-reviewer (claude opus-5-5, fresh context; did not build these units)",
 "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
 "scope": "12 units of wave-4 shard-21 (build:w4s21 in _reviewer-w4s8/build-assignments-all-waves.json): TST-0206 TST-0215 TST-0219 TST-0221 TST-0223 TST-0227 TST-0230 TST-0233 TST-0236 TST-0238 TST-0243 TST-0245",
 "transport_independence": "sha256: CRLF->LF normalized, recomputed from live bytes, re-verified after probe re-runs (battery diff before/after probes = 0, no mutation); probes: 24/24 scripts re-run live from repo root via python -B subprocess, all exit 0; schema: TWO mechanically independent transports - platform/lib/schema_resolver.py validate_artifact AND raw jsonschema Draft202012Validator against the registry-resolved physical fragment; identical error counts on every unit; schema drift ruled out: receipt.schema.json sha b258d8c9fed74de1f2297d32026aa766462a4518e56e2b1f311363740584d3fd and artifact-class-profiles.schema.json sha f89a4209d2fbb01331db87194c22be6976c0de5786fae5cdb47c3666a6e558d3 byte-identical across p2-g1 and source/ast-integrate trees",
 "witness_sweep": "schema reachability proven per class: security_report 16/24 sampled receipts validate clean, benchmark_result 9/15, ux_report 3/6 - the 12 failures are receipt defects, not schema unreachability",
 "summary": "0/12 PASS, 12/12 FAIL. Every unit fails output_schema_valid (receipt invalid against its catalog-declared output_schema on both transports). TST-0215 additionally fails not-self-declared-FAILED (sentinel FAILED:TST-0215 over state=SUCCESS) and carries a false SUCCESS envelope over REFUTED content. All probes green; all manifest sha rows live-match; the failing layer is the receipt envelope/domain payload, not the probe evidence.",
 "verdict_rule": "ANY failing check -> verdict FAIL with the precise failing check; receipt unchanged. No PASS closure was confirmable: all 12 units have at least one failing check.",
 "units": units,
}
Path("_reviewer_shard21_w4_closures.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("written", Path("_reviewer_shard21_w4_closures.json").resolve())
print("units:", len(units), "all FAIL:", all(u["verdict"] == "FAIL" for u in units.values()))
