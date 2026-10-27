#!/usr/bin/env python3
"""w3s6 RESUME (2026-10-26 ~18:38Z+2): fold the resumed independent review into the
shard verdict file. Preserves the first attempt verbatim under first_attempt."""
from __future__ import annotations

import json
from pathlib import Path

V = Path(r"C:/Users/Prekzursil/p2-g1/_p2shard6-w3-review/reviewer_wave3_shard6_verdict.json")
doc = json.loads(V.read_text(encoding="utf-8"))
first = dict(doc)

resume = {
    "resume_of": "the 2026-10-26T06:20Z reviewer agent died before returning its structured output (0 tok); review work below re-derives and re-checks everything on disk as of 2026-10-26 ~18:20-18:38 local (+0200)",
    "reviewer": "claude-opus-5-5 wave3-shard6-independent-reviewer RESUME (fresh instance; did not build these units)",
    "instruments": {
        "fresh_direct_checks": "_p2shard6-w3-review/resume_check_3red.py (strict receipt_core Draft2020-12 + declared output_schema + CRLF-normalized manifest digest recompute, re-run live at resume time)",
        "closure_field_check": "all 12 receipts' reviewer.verdict/independent/state read directly",
        "canonical_gate_crosscheck": "command-center/p2-wave/_measure_one_delivered.py re-run: BLD-0042 + BLD-0049 inline (both SUCCESS:delivered - that gate does NOT validate output_schema, so this is the narrower instrument, not a contradiction); BLD-0037 detached re-run launched, log canonical_re0037_r2.log (2700s/probe budget)",
        "fresh_full_battery": "verify_shard6_w3.py run4 launched detached 18:21, log verify_run4.log (in flight at verdict-write time; cannot change any verdict: the 9 PASS receipts+manifests are byte-identical to run3's verified state, and the 3 FAILs rest on receipt-content facts re-derived directly)",
        "program_predicate_crosscheck": "command-center/READY-UNITS.json regenerated 18:11 today by ready_units.py independently classifies BLD-0037/0042/0049 as NOT delivered (they sit in ready_units[301], not already_delivered[1331]) - second instrument agreeing with the FAIL verdicts; its ready-set failure classes: 298 schema-invalid + 3 self-declared across the 301",
    },
    "post_verdict_repair_lane_activity_2026_10_26": {
        "BLD-0037": "receipt modified 07:44 + manifest re-registered 07:59 AFTER the first verdict - but the receipt envelope is STILL incomplete (strict receipt_core errors = 41, declared output_schema errors = 42, identical counts to pre-repair full_errors.txt line 78); the receipt carries no extensions/derivation note of what changed; manifest derivation honestly lacks any envelope-repair completion claim",
        "BLD-0042": "receipt UNTOUCHED (mtime Oct 24) but manifest re-registered 07:30 still carrying the derivation claim 'envelope-repair 2026-10-26: receipt completed to the current receipt profile; rows re-hashed' - the claim remains FALSE (report.observations still absent); probe2_live_ast_recheck.py was REWRITTEN 07:30 (note: 'shard5-w4 resume 2026-10-26'): exact-line containment replaced by function-name resolution + param-default presence with line-drift REPORTED not fatal; the rewritten probe passes and still fails if the finding ceases to exist, but the receipt's bench.py:150 coordinate is confirmed stale (line 150 is still a module-level Case literal in DEFAULT_CASES; bench.py mtime 04:30 predates the original probe failure, so the receipt coordinate was never valid as a function-declaration anchor)",
        "BLD-0049": "UNTOUCHED since before the first verdict (receipt 03:48, manifest 03:59); still missing the required root report object; manifest derivation still carries the same FALSE 'receipt completed' claim",
    },
    "units": {
        "BLD-0031": {"verdict": "PASS", "note": "existing independent PASS closure (openai/gpt-5.2 C5 wave 2026-08-21) confirmed at resume; artifact/manifest byte-identical to run3-verified state"},
        "BLD-0032": {"verdict": "PASS", "note": "existing independent PASS closure (BLD-0032-probe2-hand-trace) confirmed at resume"},
        "BLD-0033": {"verdict": "PASS", "note": "existing independent PASS closure (BLD-0033-probe2-independent-queries) confirmed at resume"},
        "BLD-0035": {"verdict": "PASS", "note": "existing PASS closure confirmed at resume; reviewer_id='schema-resolver' is a tool-named stamp - noted, not a failing check (carried from first attempt)"},
        "BLD-0037": {
            "verdict": "FAIL",
            "failing_checks": [
                "C2 strict receipt_core: 41 errors re-derived live at resume (missing schema_version, spec_anchor, min_bytes_threshold, artifacts, timestamps, retry, downstream_consumers, manifest_registration, negative_controls; evidence/reviewer/tests shape) - the 07:44 post-verdict edit did NOT complete the envelope",
                "C3 declared output_schema (contradiction-register profile): 42 errors re-derived live at resume",
                "F probes: 600s-budget battery times out both probes (probe1 needs ~971s, probe2 ~1498s); at the unit-contract 3600s detached budget (07:03) probe1 FAILED (artifact unconsulted-set drift vs live ledger) and probe2 passed; canonical 2700s-budget re-run in flight (canonical_re0037_r2.log)",
            ],
            "note": "receipt unchanged by this review; repair = complete the receipt_core envelope (same operation the 03:48 batch ran on 11 of its 12 siblings), re-register manifest rows after, then re-review; probe1's ledger-drift needs a re-anchored unconsulted set",
        },
        "BLD-0040": {"verdict": "PASS", "note": "existing independent PASS closure (grok-p2-wave-BLD-0040-independent) confirmed at resume"},
        "BLD-0042": {
            "verdict": "FAIL",
            "failing_checks": [
                "C3 declared output_schema (test-quality-census profile): report.observations required and absent - re-derived live at resume; receipt untouched since Oct 24",
                "integrity: manifest re-registered 07:30 with derivation 'receipt completed to the current receipt profile' while the receipt was NOT completed - false completion claim stands",
            ],
            "note": "F is now green (probe2 rewritten 07:30, passes; semantic re-base judged defensible-but-debiasable: coordinate staleness downgraded to reported line_drift); receipt unchanged by this review; repair = add report.observations (non-empty) + correct the derivation claim",
        },
        "BLD-0043": {"verdict": "PASS", "note": "existing independent PASS closure (independent-reviewer-shard7-w2-claude-opus-fresh) confirmed at resume"},
        "BLD-0044": {"verdict": "PASS", "note": "existing independent PASS closure (openai/gpt-5.2 C5 wave 2026-08-21) confirmed at resume"},
        "BLD-0045": {"verdict": "PASS", "note": "existing independent PASS closure (BLD-0045-probe2-delete-assert-reclassify) confirmed at resume"},
        "BLD-0049": {
            "verdict": "FAIL",
            "failing_checks": [
                "C3 declared output_schema (threat-coverage-matrix profile): root report object required and entirely absent - re-derived live at resume; strict receipt_core 0 errors; manifest 4/4 digest-match; probes 2/2 rc=0",
                "integrity: manifest derivation still claims 'envelope-repair 2026-10-26: receipt completed' - FALSE, receipt lacks the required report object",
            ],
            "note": "receipt unchanged by this review; repair = add report object (kind, non-empty observations, control_ids) + correct the derivation claim",
        },
        "BLD-0050": {"verdict": "PASS", "note": "existing independent PASS closure (independent-reviewer-shard7-w2-claude-opus-fresh) confirmed at resume"},
    },
    "summary": {
        "units_total": 12,
        "pass": 9,
        "fail": 3,
        "verdict": "PARTIAL (confirmed at resume) - 9/12 hold ALL checks with valid independent closures; 3/12 FAIL (BLD-0037 C2+C3[+F-at-contract-budget], BLD-0042 C3, BLD-0049 C3) with precise failing checks; no receipt was modified by either review pass",
    },
    "program_progress_context_for_owner": {
        "as_of": "command-center/READY-UNITS.json regenerated 2026-10-26 18:11",
        "delivered": "1331/2007 (66.3%)",
        "not_delivered": "676 = ready 301 + owner_gated 67 + blocked 308 (296 unbuilt-dependency + 12 unknown-token)",
        "artifact_surface": "all 2007 catalog output_paths exist and parse; 1994 claim state=SUCCESS - the 676 delta is the schema-invalid-claiming-SUCCESS envelope class (same family as this shard's 3 red units)",
    },
}

doc.clear()
doc["wave"] = first["wave"]
doc["shard"] = first["shard"]
doc["resume_2026-10-26"] = resume
doc["first_attempt_2026-10-26T06:20Z"] = first
V.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("VERDICT-UPDATED", V)
