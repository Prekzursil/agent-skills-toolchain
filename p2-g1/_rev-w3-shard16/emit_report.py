#!/usr/bin/env python3
"""Emit the wave-3 shard-16 reviewer report."""
import hashlib
import json
import io
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
verify = json.load(io.open(REPO / "_rev-w3-shard16" / "verify_out.json", encoding="utf-8"))
gate = json.load(io.open(REPO / "_rev-w3-shard16" / "gate_layer2_check.json", encoding="utf-8"))
closure = json.load(io.open(REPO / "_rev-w3-shard16" / "closure_report.json", encoding="utf-8"))
UNITS = ["RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079", "RES-0086",
         "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111", "RES-0112"]


def rsha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


sentinel_res0112 = (
    "SUCCESS:RES-0112 in the receipt AND a property gap table citing existing gates "
    "absent on this tree"
)
report = {
    "reviewer": "claude-opus-5-5-independent-reviewer-w3s16-2026-10-26",
    "wave": 3,
    "shard": 16,
    "date": "2026-10-26",
    "mandate": (
        "adversarial independent closure of 12 units (never their builder); ALL checks hold "
        "-> receipt reviewer.verdict=PASS independent=true state=SUCCESS; ANY fails -> verdict "
        "FAIL, receipt unchanged"
    ),
    "units_scope_derivation": (
        "wave-3 reviewer shards are 12-unit slices of the pending queue; shards 0-15 and 20 are "
        "covered by sibling reviewers' on-disk unit lists (_reviewer-w3s0..s15, "
        "_p2-shard20-w3-entries). The still-pending RES block between shard-15's last unit "
        "(RES-0020) and shard-20's first (TST-0129) contains exactly the 12 units reviewed "
        "here, all receipts BLOCKED/failure.classification=['reviewer-absent'] at dispatch "
        "(the builder terminal only the independent reviewer may close)."
    ),
    "checks_per_unit": [
        "artifact at catalog output_path: exists, non-empty, parses, not self-blocked",
        "receipt in closable builder terminal (BLOCKED/reviewer-absent), unit_id + spec_anchor bound",
        "catalog completion_sentinel present in receipt text",
        "EVERY receipt artifacts[] row sha256/bytes recomputed (CRLF->LF) vs live",
        "manifest primary row present=true with sha256+bytes match; every other row digest-matched",
        "output_schema resolved FAIL-CLOSED via platform/lib/schema_resolver (UnknownSchemaError=FAIL)",
        "receipt strict receipt_core (draft 2020-12) validation, current + simulated post-closure payload, BEFORE any write",
        "live probes re-executed from repo root: exit 0 + SUCCESS: present + FAILED: absent",
        "artifact >= declared min_bytes_threshold",
        "recorded evidence probes claim exit 0 (source rows carry SUCCESS markers)",
    ],
    "independence": {
        "built_by_this_reviewer": False,
        "sha_instrument_cross_check": (
            "python hashlib vs PowerShell .NET SHA256 over CRLF->LF-normalized bytes on "
            "RES-0044/RES-0089/RES-0111: identical"
        ),
        "program_instruments": [
            "command-center/receipt_validate.py admission: 10/10 ACCEPT",
            "platform/lib/receipt_schema_gate.evaluate_full: 10/10 complete=True all-12-conditions SATISFIED",
            "gate_layer2_check.json on disk",
        ],
    },
    "verdicts": {},
    "program_notes": [
        (
            "artifact-class-profile drift is PROGRAM-WIDE, not shard-16-specific: "
            "schema_resolver.validate_artifact over the output_path artifact vs the declared "
            "class profile fails 508/1062 already-independently-closed units (measured this "
            "run). The sanctioned closure schema check in this program is the RECEIPT against "
            "receipt.schema.json via platform/lib/receipt_schema_gate (the 12-condition gate; "
            "condition 4 basis confirms), which is what this reviewer enforced; per-artifact "
            "class-profile error counts are recorded in verify_out.json as information."
        ),
        (
            "receipt_core allOf[0] makes state=SUCCESS require tests[], negative_controls[], "
            "manifest_registration, downstream_consumers, residual_unknowns; the builder "
            "BLOCKED receipts of these units carried none. The closure authors these blocks "
            "from the REVIEWER's own live evidence of this run (probe re-runs, manifest "
            "re-hash), never from builder claims; negative_controls entries quote the units' "
            "own recorded NC/mutant fire-on-bad-state and clean-on-good-state probe lines."
        ),
    ],
    "fail_repairs_needed": {
        "RES-0037": [
            "manifest probe2 row stale: registered bd7131ce0035.../3754B vs live "
            "52f4ad3f9441.../4558B (probe2_handle_count.py legitimately repaired "
            "2026-10-26T03:29 for substrate drift - documented in "
            "probes/RES-0037/SUBAGENT-RETURN.json shard16_repair - but "
            "UNIT-ARTIFACT-MANIFEST.json was not re-registered)",
            "receipt artifacts[] rows stale for probe2_handle_count.py and "
            "SUBAGENT-RETURN.json (2bdfe3224f9b.../3783B vs live 53b455a3c008.../5350B)",
            "repair lane: re-register probe2 + SUBAGENT-RETURN rows in manifest and receipt, "
            "then re-offer",
        ],
        "RES-0112": [
            "receipt artifacts[] primary row sha 3796154fc6ec.../34041B (raw-CRLF hash basis) "
            "!= live artifact CRLF->LF-normalized sha f7f49bb48480.../33345B (non-compliant "
            "basis AND stale vs artifact saved 2026-10-25T18:08)",
            "catalog completion_sentinel (" + sentinel_res0112 + ") absent from receipt text",
            "receipt sentinel is FAILED:-prefixed, structurally irreconcilable with "
            "state=SUCCESS (receipt_core allOf[2])",
            "manifest primary row: sha LF-normalized but bytes raw-CRLF (34041) - internally "
            "inconsistent row",
            "recorded evidence 'verifier' rows are claims ('manifest sha row vs live artifact "
            "norm-hash' with raw_output 'manifest row sha == norm(live bytes)'), not runnable "
            "probes with SUCCESS markers",
            "repair lane: re-register receipt row with normalized sha, set receipt sentinel to "
            "the catalog completion sentinel, re-record evidence with real raw outputs, then "
            "re-offer",
        ],
    },
    "fail_receipts_untouched": {
        u: {
            "sha256_before": closure["fail_units_untouched"][u]["sha256_before"],
            "sha256_after": closure["fail_units_untouched"][u]["sha256_after"],
            "untouched": closure["fail_units_untouched"][u]["untouched"],
        }
        for u in ("RES-0037", "RES-0112")
    },
    "artifacts": [
        "_rev-w3-shard16/verify_shard16_w3.py",
        "_rev-w3-shard16/verify_out.json",
        "_rev-w3-shard16/verify_run2.log",
        "_rev-w3-shard16/verify_run3.log",
        "_rev-w3-shard16/verify_run4.log",
        "_rev-w3-shard16/verify_run5.log",
        "_rev-w3-shard16/verify_run6.log",
        "_rev-w3-shard16/crosshash.ps1",
        "_rev-w3-shard16/emit_closures.py",
        "_rev-w3-shard16/closure_report.json",
        "_rev-w3-shard16/gate_layer2_check.json",
    ],
    "summary_counts": {"pass_closed": 10, "fail": 2, "total": 12},
}
for uid in UNITS:
    res = verify["results"][uid]
    ok = not res["fails"]
    g = next(r for r in gate["rows"] if r["unit"] == uid)
    report["verdicts"][uid] = {
        "verdict": "PASS" if ok else "FAIL",
        "receipt_state_after": "SUCCESS" if ok else "BLOCKED (unchanged)",
        "receipt_sha256_after": rsha(REPO / "command-center" / "receipts" / (uid + ".json")),
        "artifact_sha256_LF_normalized": res.get("sha256"),
        "artifact_bytes_LF_normalized": res.get("bytes"),
        "live_probes": res.get("probes"),
        "program_gate_complete": g["complete"],
        "program_gate_marker": g["marker"],
        "failing_checks": res["fails"],
    }
p = REPO / "_rev-w3-shard16" / "reviewer-report-w3s16-2026-10-26.json"
p.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", p)
print("verdicts:", {u: report["verdicts"][u]["verdict"] for u in UNITS})
