#!/usr/bin/env python3
"""Emit wave-3-shard-8 reviewer closure record from the verify + predicate runs.

Reads:
  _reviewer_w3s8_verdicts.json    (independent verifier, direct-subprocess transport)
  _reviewer_w3s8_predicate_out.json (platform completion_predicate per receipt)

Writes _reviewer_w3s8_closures.json. Receipts are NOT modified - any unit with
any failing check keeps its receipt byte-identical and stays open.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
raw = json.loads((REPO / "_reviewer_w3s8_verdicts.json").read_text(encoding="utf-8"))
pred = json.loads((REPO / "_reviewer_w3s8_predicate_out.json").read_text(encoding="utf-8"))

# resolver error counts / first errors measured live 2026-10-26 by
# platform.lib.schema_resolver.validate_artifact(doc, catalog output_schema)
resolver = {
    "CNF-0152": (12, "<root>: 'report' is a required property"),
    "CNF-0164": (3, "artifacts/5/role: 'named-probe' is not one of ['primary','supporting','log','fixture','control']"),
    "CNF-0167": (5, "<root>: 'report' is a required property; produced_by: 'command-center/p2-wave/probes/CNF-0167/emit_report.py' is not of type 'object'"),
    "CNF-0169": (3, "<root>: 'downstream_consumers' is a required property; 'residual_unknowns' required; open P1 defects D-CNF0169-NAMESPACE-SPLIT / D-CNF0169-UNKEYED-MANIFEST"),
    "CNF-0171": (1, "<root>: 'downstream_consumers' is a required property"),
    "CNF-0172": (2, "tests: dict is not of type 'array'"),
    "CNF-0177": (1, "reviewer: Additional properties not allowed ('n_tasks','requirement','tasks_path')"),
    "CNF-0184": (42, "<root>: 'downstream_consumers'/'manifest_registration'/'negative_controls' required"),
    "CNF-0188": (8, "reviewer: Additional properties not allowed; tests/0..1: 'pass' unexpected"),
    "CNF-0191": (10, "artifacts/0..: 'bytes'/'sha256' required"),
    "CNL-0078": (1, "spec_anchor: object shape vs required string anchor (sibling CNL-0076 uses string anchor)"),
    "IMP-0002": (6, "artifacts/1/role: 'implementation' not in enum; reviewer: 'note' unexpected"),
}

closures = {
    "reviewer": "wave-3-shard-8-independent-reviewer (claude opus-5-5, fresh context)",
    "date": "2026-10-26",
    "scope": "12 units of build:w3s8 (_reviewer-w4s8/build-assignments-all-waves.json): "
             "CNF-0152, CNF-0164, CNF-0167, CNF-0169, CNF-0171, CNF-0172, CNF-0177, "
             "CNF-0184, CNF-0188, CNF-0191, CNL-0078, IMP-0002",
    "transport_independence": (
        "artifact/sha/probe checks re-derived from bytes via direct sys.executable "
        "subprocess; schema leg validated by TWO mechanically independent oracles "
        "(platform.lib.schema_resolver registry profile + direct shim-file "
        "jsonschema validation, agreeing); platform completion_predicate (12 "
        "conditions) run as third corroboration"
    ),
    "detector_control": (
        "sibling controls under the same oracles: IMP-0074/IMP-0076/IMP-0090/"
        "IMP-0146/CNF-0146/CNL-0076/IMP-0001 are schema-valid (0 errs); ADV-0038 "
        "(52 errs) and RES-0037 (16 errs) fail corpus-wide - conformance is "
        "achievable and enforced elsewhere, so shard-8 violations are real, not "
        "an instrument artifact"
    ),
    "units": {},
}
for uid, r in raw["units"].items():
    ok = r["ok"]
    p = pred.get(uid)
    info = r["info"]
    fails = list(r["fails"])
    if not ok:
        rc, fe = resolver.get(uid, (None, None))
        units_row = {
            "verdict": "FAIL",
            "receipt_state": info.get("receipt_state"),
            "closure_doc": info.get("closure_src"),
            "reviewer_in_receipt": {
                "verdict": info.get("reviewer_verdict"),
                "independent": info.get("reviewer_independent"),
            },
            "evidence": {
                "artifact_bytes": info.get("bytes"),
                "sha256_lf_normalized": info.get("sha256"),
                "manifest_sha_row": "MATCHES live artifact" if "manifest-sha-row-mismatch" not in fails else "MISMATCH",
                "probe_rcs": {k: v for k, v in info.items() if k.startswith("probe_")},
                "schema_resolver_errs": rc,
                "schema_resolver_first": fe,
                "predicate_verdict": p["verdict"] if p else "NOT-RUN(no-receipt)",
                "predicate_unsatisfied": p["not_satisfied"] if p else None,
            },
            "failing_checks": fails,
            "closure_action": "receipt unchanged; unit stays open pending rebuild",
        }
    else:
        units_row = {
            "verdict": "PASS",
            "receipt_state": info.get("receipt_state"),
            "closure_action": "existing PASS closure confirmed, receipt stays SUCCESS",
            "failing_checks": [],
        }
    closures["units"][uid] = units_row

closures["summary"] = {
    "pass": sorted(u for u, r in closures["units"].items() if r["verdict"] == "PASS"),
    "fail": sorted(u for u, r in closures["units"].items() if r["verdict"] == "FAIL"),
    "all_ok": raw["all_ok"],
    "headline_defects": {
        "CNF-0171": "receipt declares command-center/p2-wave/probes/CNF-0171/structural-identity-report.txt exists=true; the file is ABSENT on disk (predicate C2 UNSATISFIED) - fabricated artifact row",
        "CNF-0152": "receipt self-declares bytes=21057, disk has 27535 (stale internal measurement); schema-invalid (reproduction-matrix profile requires 'report'); evidence[0] CONFIRMED with no VERIFIER probe",
        "IMP-0002": "receipt self-declares bytes=9158, disk has 9218 (edited post-finalize without remeasure); 6 schema violations (role enum, reviewer.note)",
        "CNF-0184": "42 schema violations vs reproduction-matrix profile; no negative_controls; no downstream consumer",
        "CNF-0169": "2 OPEN P1 defects in receipt (D-CNF0169-NAMESPACE-SPLIT, D-CNF0169-UNKEYED-MANIFEST) contradict SUCCESS closure rule",
        "CNL-0078": "spec_anchor is an object; councilspec.v2 profile + sibling CNL-0076 require a string anchor",
    },
}

closures["notes"] = {
    "probe_marker_entries": (
        "probe-*-marker FAILCHECK rows for CNF-0152/CNF-0167 are INFORMATIONAL, "
        "not contract violations: this shard's probes exit 0 and emit JSON "
        "'all_ok': true payloads rather than SUCCESS: markers; the contract leg "
        "is exit code 0, which every probe on every unit satisfied. No unit's "
        "verdict rests on the marker check."
    ),
    "schema_leg_double_oracle": (
        "every unit fails output_schema under BOTH the platform resolver "
        "(registry profile) and direct shim-file jsonschema validation; the "
        "platform 12-condition completion_predicate independently reports "
        "INCOMPLETE on all 11 receipt units"
    ),
}

OUT = REPO / "_reviewer_w3s8_closures.json"
OUT.write_text(json.dumps(closures, indent=1, ensure_ascii=False) + "\n",
               encoding="utf-8", newline="\n")
print("wrote", OUT)
for uid in sorted(closures["units"]):
    u = closures["units"][uid]
    print(uid, u["verdict"], "| resolver_errs:", u["evidence"].get("schema_resolver_errs") if u["verdict"] == "FAIL" else "-")
print("SUCCESS:w3s8-reviewer closures emitted" if all(r["verdict"] == "PASS" for r in closures["units"].values())
      else "FAILED:w3s8-reviewer %d/12 units FAIL - receipts unchanged" % len(closures["summary"]["fail"]))
