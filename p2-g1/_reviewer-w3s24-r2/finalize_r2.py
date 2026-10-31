#!/usr/bin/env python3
"""Finalize r2 verdicts: augment fail reasons with precise findings + provenance."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
vp = HERE / "verdicts.json"
v = json.loads(vp.read_text(encoding="utf-8"))

reasons = {
    "TST-0215": (
        "NOT DELIVERED / FAIL. Receipt at command-center/receipts/TST-0215.json is "
        "self-declared BLOCKED (state=BLOCKED, sentinel FAILED:TST-0215 ..., "
        "failure.classification=[reviewer-absent, open-production-defect], reviewer_gate "
        "0/2, reviewer.verdict=NOT-REVIEWED/independent=false). The block is honest and "
        "live-true: this reviewer re-ran probe1_detector_control.py (exit 0) and its "
        "output records planted_capability_selected=true, i.e. the open P1 defect "
        "TST0215-F1 (repository router steerable by package-owned capability prose) "
        "reproduces on the live tree today; the receipt also carries open P1 TST0215-F1 "
        "+ P2 TST0215-F2 and 3 result=FAIL test rows (ROUTING-INVARIANCE, "
        "TOOL-SEQUENCE-INVARIANCE, CONDITION-11). receipt_core forbids SUCCESS with a "
        "FAILED sentinel or open P0/P1 defect; only the independent reviewer closes and "
        "the closing conditions are not met. Receipt left byte-unchanged (verified "
        "before/after)."
    ),
    "TST-0223": (
        "FAIL: declared output_schema invalid. Catalog output_schema "
        "command-center/schema/receipt.schema.json#/$defs/security_report resolves (via "
        "artifact-class-profiles) to the physical security_report def, which allOf "
        "receipt_core AND requires report (kind const security_report). The receipt has "
        "NO report property (only top-level report_kind='security_report'). Error "
        "reproduced by 3 instruments: program resolver validate_artifact, direct "
        "Draft202012Validator at the canonical BASE_URI ref, and direct key inspection. "
        "receipt_core-only validation passes (0 errors), which is how a core-only "
        "instrument would miss this. All other checks green (probes exit 0/0, manifest "
        "LF sha match on all rows, reviewer PASS+independent, content scan clean). "
        "Receipt left byte-unchanged."
    ),
    "TST-0227": (
        "FAIL: declared output_schema invalid - identical shape to TST-0223. Catalog "
        "output_schema ...#/$defs/security_report requires report; receipt carries only "
        "top-level report_kind='security_report', no report property. Reproduced by 3 "
        "instruments (program resolver, direct Draft202012Validator, direct key "
        "inspection); receipt_core-only passes. All other checks green (probes exit 0/0, "
        "manifest LF sha match all rows, reviewer PASS+independent, content clean). "
        "Receipt left byte-unchanged."
    ),
    "TST-0233": (
        "FAIL: declared output_schema invalid - same shape, benchmark_result class. "
        "Catalog output_schema ...#/$defs/benchmark_result requires report (kind const "
        "benchmark_result); receipt carries only top-level report_kind="
        "'benchmark_result', no report property. Reproduced by 3 instruments (program "
        "resolver, direct Draft202012Validator, direct key inspection); "
        "receipt_core-only passes. All other checks green (probes exit 0/0, manifest LF "
        "sha match all rows, reviewer PASS+independent, content clean). Receipt left "
        "byte-unchanged."
    ),
}
for uid, r in reasons.items():
    v["verdicts"][uid]["fail_reason"] = r

v["shard_derivation"] = (
    "wave-3 shard 24 = pendingReview[288:296] (last 8 of 296), matching the earlier "
    "_reviewer-w3s24 attempt's unit list; all 8 verified against "
    "command-center/WORK-UNIT-CATALOG.json (all present, output_path + output_schema "
    "declared, no owner_approval_required, no unknown dependency tokens). No sibling "
    "reviewer result mentions these 8 units."
)
v["staleness_note"] = (
    "Every one of the 8 receipts was REBUILT after the earlier _reviewer-w3s24 run "
    "(receipt mtimes 19:51-20:19 vs that review's 06:32 verdicts; every prior recorded "
    "receipt sha256 differs from the live bytes), so the earlier verdicts were stale "
    "for all 8 units and this r2 re-derived every check from current disk state. "
    "Current UNIT-ARTIFACT-MANIFEST rows match the current receipt bytes (LF mode) on "
    "every row of every unit."
)
v["closure_note"] = (
    "The 4 PASS units (TST-0206, TST-0219, TST-0221, TST-0230) already carry valid "
    "PASS+independent closures (reviewer ids: schema-resolver / "
    "TST-0219-probe2-independent-tree-hash / grok-p2-wave-TST-0221-independent / "
    "grok-p2-deliver-TST-0230-xai). Per the confirm-path of the unit contract, the "
    "receipt bytes are left untouched because the artifact IS the receipt and the "
    "manifest sha256 rows match the live bytes - any edit would flip the canonical "
    "measure to manifest-sha-mismatch and un-deliver a green unit. This reviewer's "
    "independent live re-verification (probes, shas, schema, content) is recorded in "
    "this file and is the r2 closing review. Recorded oddity, non-gating: TST-0206's "
    "historical reviewer_id is 'schema-resolver' (a tool name); its verdict=PASS and "
    "independent=true fields hold and every load-bearing fact was re-proven live by "
    "this reviewer, so the enumerated checks hold."
)
v["summary"] = {
    "pass": sum(1 for x in v["verdicts"].values() if x["verdict"] == "PASS"),
    "fail": sum(1 for x in v["verdicts"].values() if x["verdict"] == "FAIL"),
    "pass_units": [u for u, x in v["verdicts"].items() if x["verdict"] == "PASS"],
    "fail_units": [u for u, x in v["verdicts"].items() if x["verdict"] == "FAIL"],
}
vp.write_text(json.dumps(v, indent=1), encoding="utf-8")
print(json.dumps(v["summary"]))
