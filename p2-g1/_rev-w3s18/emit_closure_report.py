#!/usr/bin/env python3
"""Emit the w3s18 reviewer closure report from verify_out.json.

Verdict rule (from the unit contract): ALL contract checks hold -> close
(stamp or confirm); ANY check fails -> verdict FAIL with the precise failing
check, receipt UNCHANGED. Every unit in this shard fails exactly one contract
check: `validate output_schema` (measured with the repo's own
platform/lib/schema_resolver.py against the catalog's declared output_schema).
Everything else verifies green live: artifacts parse non-empty, both named
probes exit 0 with pass-verdicts re-run by this reviewer, every
UNIT-ARTIFACT-MANIFEST.json digest-matches the live bytes (CRLF normalized).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
RAW = REPO / "_rev-w3s18" / "verify_out.json"
OUT = REPO / "_rev-w3s18" / "closure_report.json"

raw = json.loads(RAW.read_text(encoding="utf-8"))
units = raw["units"]
results = raw["results"]

closures = {
    "reviewer": "wave-3-shard-18-independent-reviewer (claude opus-5-5, fresh context)",
    "date": "2026-10-26",
    "scope": ("12 units of build:w3s18 (RES-0179, RES-0180, RES-0182, TST-0018, "
              "TST-0028, TST-0032, TST-0057, TST-0060, TST-0066, TST-0067, "
              "TST-0068, TST-0070)"),
    "verdict_rule": ("ALL contract checks hold -> close (stamp PASS/independent/SUCCESS "
                     "or confirm); ANY fails -> FAIL with the precise failing check, "
                     "receipt unchanged. Fail-closed: a dishonest PASS is worse than a "
                     "partial shard."),
    "transport_independence": (
        "all checks re-derived from live bytes by this reviewer: direct "
        "sys.executable subprocess probe re-runs (plain env, PYTHONPATH stripped), "
        "CRLF-normalized sha256 recomputes, and validation via the repo's own "
        "platform/lib/schema_resolver.py + platform/schema/receipt.schema.json "
        "#/$defs/receipt_core (draft 2020-12, jsonschema 4.25.1) - not the "
        "builder's transport"),
    "verified_green_live_all_units": [
        "artifact at catalog output_path: exists, non-empty, parses as JSON, no content-reason self-block",
        "all 24 named probes re-run by this reviewer exit 0 with pass-verdicts "
        "(SUCCESS: markers or structured JSON pass=true, red=[]); 5 TST probes use "
        "structured-JSON verdicts without a SUCCESS: text marker by design - noted, not failed",
        "every UNIT-ARTIFACT-MANIFEST.json primary row present=true and digest-matches "
        "the live artifact (sha256 over CRLF-normalized bytes); every supporting row digest-matches",
    ],
    "single_failing_check_all_units": (
        "check 4 `validate output_schema`: the artifact at output_path violates its "
        "catalog-declared output_schema (validated with the repo's own resolver). "
        "For the 9 TST units the artifact IS the receipt, so the SUCCESS receipts "
        "themselves are schema-invalid; for the 3 RES units the research payloads "
        "lack the required receipt-core envelope (the same shape defect the "
        "shard-17 builder repaired on its 9 units before its reviewer closed them)."),
    "receipts": [],
    "summary": {},
}

for uid in units:
    r = results[uid]
    ok = not r["fails"]
    closures["receipts"].append({
        "unit_id": uid,
        "receipt_path": r.get("receipt_path"),
        "output_path": r.get("out_rel"),
        "receipt_state": r.get("receipt_state"),
        "verdict": "PASS" if ok else "FAIL",
        "receipt_modified_by_reviewer": False,
        "live_sha256_crlf_normalized": r.get("sha256_live"),
        "live_bytes_crlf_normalized": r.get("bytes_live"),
        "output_schema_violations": r.get("output_schema_violations"),
        "output_schema_first_errors": (r.get("schema_errors_head") or [])[:4],
        "receipt_core_errors_as_is": r.get("core_errors"),
        "failing_checks": r["fails"],
        "closable_pending_builder_repair": (r.get("receipt_state") == "BLOCKED"
                                            and "reviewer-absent" in (r.get("fcls") or [])),
        "probes_ok": sum(1 for p in r.get("probe_runs", []) if p.get("verdict")),
        "probe_runs_total": len(r.get("probe_runs", [])),
        "closure_action": ("receipt unchanged" if not ok else
                           ("existing PASS closure confirmed, stays SUCCESS" if r.get("confirm_only")
                            else "stamped PASS/independent/SUCCESS")),
    })

p = sorted(x["unit_id"] for x in closures["receipts"] if x["verdict"] == "PASS")
f = sorted(x["unit_id"] for x in closures["receipts"] if x["verdict"] == "FAIL")
closures["summary"] = {
    "pass": p,
    "fail": f,
    "pass_count": len(p),
    "fail_count": len(f),
    "shard_green": len(f) == 0,
    "systemic_note": (
        "Control check: receipts of units ALREADY closed by sibling reviewers "
        "(TST-0092, TST-0116, IMP-0321, IMP-0423, TST-0090, TST-0091) also carry "
        "5-38 receipt_core violations each. The schema's own x-measured-conformance "
        "block states 'No real work-unit receipt produced by another unit has been "
        "validated against it'. So this is a program-wide receipt-shape debt, not a "
        "shard-18-only defect; this reviewer fails its own shard honestly rather "
        "than deepen the debt with more non-conforming closures."),
    "repair_prescription": (
        "Builder-side repair lane (precedent: _p2shard17-w3-repair-receipts.py): "
        "(1) RES-0179/0180/0182 - envelope the live research payloads into the "
        "receipt-core shape their catalog output_schema declares (research-claim-record / "
        "measurement-run / design-spec profiles all $ref generic_report = receipt_core + "
        "report.kind), preserving the payload under report.observations/report payload, "
        "and add evidence (the two live probe pairs), retry, negative_controls, "
        "downstream_consumers, residual_unknowns; (2) TST receipts - add the missing "
        "receipt_core required fields, fix tests rows to the test_result shape "
        "(id/command/result), remove unexpected props (manifest_registration.derivation, "
        "evidence extra props, non-enum probe methods) into extensions, drop or re-shape "
        "the stale self-referential artifacts rows (a receipt describing itself can never "
        "carry its own live sha - fixed-point impossible; the binding hash surface is "
        "UNIT-ARTIFACT-MANIFEST.json, which already digest-matches live on all 12 units); "
        "(3) then re-dispatch this reviewer: probes and manifests already verify green "
        "live, so a repair that only fixes receipt shape closes in one reviewer pass."),
}

OUT.write_text(json.dumps(closures, indent=1, ensure_ascii=False) + "\n",
               encoding="utf-8", newline="\n")
print("wrote", OUT)
print(("FAILED:" if f else "SUCCESS:") +
      f"w3s18 reviewer closures: pass={len(p)} fail={len(f)} "
      f"(single failing check: validate output_schema; probes+manifests green live on all 12)")
for x in closures["receipts"]:
    print(f"  {x['unit_id']}: {x['verdict']} "
          f"(schema_viol={x['output_schema_violations']}, core_err={x['receipt_core_errors_as_is']}, "
          f"receipt={x['receipt_state']}, receipt_unchanged={x['receipt_modified_by_reviewer'] is False})")
