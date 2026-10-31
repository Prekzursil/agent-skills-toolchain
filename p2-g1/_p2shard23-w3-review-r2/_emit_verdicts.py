"""Build VERDICTS-w3s23-r2.json from _w3s23r2_results.json + manual reads.

Verdict rule (fail-closed): unit PASS only if every check passed.
On any fail -> verdict FAIL, receipts untouched.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
results = json.loads((HERE / "_w3s23r2_results.json").read_text(encoding="utf-8"))

MANUAL = {
    "TST-0204": "dishonest SUCCESS: sentinel 'FAILED:TST-0204 ... condition 11 is live-red' "
                "under state=SUCCESS; open P1 defect TST-0204-F1; test TST0204-TR1-ROOT-CAP-PROPERTY not PASS; "
                "downstream_consumers empty under state=SUCCESS",
    "TST-0215": "dishonest SUCCESS: sentinel 'FAILED:TST-0215 fresh refute probes show capability text steers the "
                "repository router...' under state=SUCCESS; open P1 defect TST0215-F1 (router steering, builder "
                "confirms live); 3 non-PASS tests; downstream_consumer executed=false read_ok=false",
    "TST-0195": "builder-era reviewer_id 'TST-0195-probe2-windows-warning-and-silent-mutant' is a probe id, not an "
                "independent reviewer; downstream_consumers[0].executed=false under state=SUCCESS",
    "TST-0197": "builder-era reviewer_id 'TST-0197-probe2-dir-listing' (probe id, not independent reviewer); "
                "downstream_consumers empty under state=SUCCESS",
    "TST-0202": "skeletal builder-era receipt: missing required core fields schema_version/spec_anchor/min_bytes_"
                "threshold/timestamps/retry/manifest_registration/downstream_consumers/residual_unknowns; artifacts[] "
                "roles 'implementation'/'probe' outside enum; evidence items missing anchor/verdict/probes and carry "
                "non-schema keys; negative_controls[0] missing kind; reviewer block carries non-schema keys; "
                "reviewer_id 'TST-0202-probe2-readlink-f-and-bash' is a probe id, not an independent reviewer",
    "TST-0206": "builder-era reviewer_id 'schema-resolver' (tool id, not independent reviewer)",
    "TST-0219": "builder-era reviewer_id 'TST-0219-probe2-independent-tree-hash' (probe id); downstream_consumer "
                "executed=false read_ok=false; consumer row missing required probe",
    "TST-0221": "builder-era reviewer_id 'grok-p2-wave-TST-0221-independent' (builder-asserted, unverifiable); "
                "downstream_consumer row missing required probe; P0/P1 defects present but resolved",
    "TST-0223": "builder-era reviewer_id 'TST-0223-probe2-mutation-widen' (probe id); downstream_consumers/manifest_"
                "registration/min_bytes_threshold/negative_controls absent under state=SUCCESS",
    "TST-0227": "builder-era reviewer_id 'TST-0227-probe2-concurrent-review' (probe id); downstream_consumer "
                "executed=false read_ok=false; report absent",
    "TST-0230": "builder-era reviewer_id 'grok-p2-deliver-TST-0230-xai' (builder-asserted, unverifiable); evidence "
                "probe method 'test-run'/'schema-validate' outside method enum; receipt references superseded "
                "generation's probe set",
    "TST-0233": "builder-era reviewer_id 'TST-0233-probe2-worse-than-sources' (probe id); report+retry absent; "
                "artifacts[0] missing bytes/sha256; downstream_consumer executed=false read_ok=false",
}

verdicts = {}
for uid, r in results.items():
    checks = r["checks"]
    failing = []
    if not checks["receipt"]["pass"]:
        failing.append("receipt: " + str(checks["receipt"].get("why", "self-declared failure state")))
    if not checks["manifest"]["pass"]:
        failing.append("manifest: " + "; ".join(checks["manifest"].get("bad_rows", [])))
    if not checks["probes"]["pass"]:
        bad = [k for k, v in checks["probes"]["results"].items() if not v["pass"]]
        failing.append(f"probes: {bad}")
    if not checks["schema"]["pass"]:
        ea = checks["schema"]["instrument_A_resolver_errors"]
        eb = checks["schema"]["instrument_B_whole_doc_errors"]
        failing.append(f"output_schema non-conformance (resolver={len(ea)}, whole-doc={len(eb)}): "
                       + " | ".join(ea[:3]))
    verdicts[uid] = {
        "verdict": "PASS" if r["unit_pass"] else "FAIL",
        "failing_checks": failing,
        "detail": MANUAL.get(uid, ""),
        "probes_rerun": {k: {"bash_exit": v["bash"]["exit"], "pwsh_exit": v["pwsh"]["exit"],
                             "divergence": v["second_shell_divergence"]}
                         for k, v in checks["probes"]["results"].items()},
    }

out = {
    "wave": "3",
    "shard": "23",
    "review": "r2 (independent re-review of the same 12 units; fresh instruments, "
              "second-shell probe protocol, corrected manifest bytes convention)",
    "units": len(results),
    "total_pass": sum(1 for v in verdicts.values() if v["verdict"] == "PASS"),
    "total_fail": sum(1 for v in verdicts.values() if v["verdict"] == "FAIL"),
    "receipts_modified": False,
    "verdicts": {u: v["verdict"] for u, v in verdicts.items()},
    "per_unit": verdicts,
}
(HERE / "VERDICTS-w3s23-r2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({u: v["verdict"] for u, v in verdicts.items()}, indent=0))
print("total_pass:", out["total_pass"], "total_fail:", out["total_fail"])
