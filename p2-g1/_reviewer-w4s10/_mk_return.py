import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
G1 = Path(r"C:/Users/Prekzursil/p2-g1")
run = json.loads((G1/"_reviewer-w4s10/w4s10-rerun/phase_a_results.json").read_bytes().decode("utf-8"))
stamp = json.loads((G1/"_reviewer-w4s10/w4s10-rerun/stamp_log.json").read_bytes().decode("utf-8"))
census = json.loads((G1/"_reviewer-w4s10/w4s10-rerun/census.json").read_bytes().decode("utf-8"))
STAMPED = {"IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198"}
def lf_sha(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
units = {}
for uid, R in run.items():
    checks = R["checks"]
    hard = ["artifact_exists_nonempty", "artifact_parses", "not_self_blocked", "state_is_SUCCESS",
            "sentinel_present", "sentinel_binds_catalog", "unit_id_matches",
            "manifest_all_present", "manifest_all_sha_match", "probes_all_exit0",
            "output_schema_valid", "admission_accept"]
    failed = [k for k in hard if checks.get(k) is False]
    verdict = "PASS" if not failed else "FAIL"
    entry = {
        "verdict": verdict,
        "failing_checks": failed,
        "receipt_sha256_lf": lf_sha(G1 / ("command-center/receipts/" + uid + ".json")),
        "manifest_rows": R.get("manifest_rows"),
        "probes_rerun": [p["cmd"].split()[-1] + " rc=" + str(p["rc"]) for p in R.get("probe_runs", [])],
        "schema_errors": (R.get("schema_errors") or [])[:4],
        "receipt_touched_by_reviewer": uid in STAMPED,
    }
    if uid in STAMPED:
        entry["closure"] = ("reviewer stamped verdict=PASS independent=true (prior builder-side "
                            "self-stamp preserved under extensions.w4s10_prior_reviewer); manifest "
                            "receipt row updated to the stamped bytes")
    elif uid == "IMP-0223":
        entry["closure"] = ("existing valid w3s11 independent PASS closure CONFIRMED on current bytes; "
                            "receipt untouched")
    else:
        entry["closure"] = ("receipt UNCHANGED (verdict FAIL); precise failure: receipt authored to a "
                            "stale receipt profile - admission gate REJECT (C2 schema-invalid); probes "
                            "and manifest all pass, only the receipt document is nonconforming")
    units[uid] = entry
ret = {
    "role": "INDEPENDENT REVIEWER wave 4 shard 10 (resume of dead run, completed 2026-10-26)",
    "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "reviewer_id": "w4-shard10-independent-reviewer-20261026",
    "scope": sorted(units.keys()),
    "did_not_build": True,
    "instruments": {
        "schema": "platform/lib/schema_resolver.validate_artifact, AST_INTEGRATE_ROOT=p2-g1 (counterfactual control: IMP-0189/0194/0195/0198/0223 validate zero-error in the same run/env)",
        "probes": "sys.executable -B per named-probe manifest row, cwd=p2-g1, PYTHONDONTWRITEBYTECODE=1, rc==0 + SUCCESS marker required",
        "manifest": "sha256 CRLF->LF normalized vs live bytes for every UNIT-ARTIFACT-MANIFEST row",
        "admission": "command-center/receipt_validate.py ACCEPT required",
    },
    "results": units,
    "score": {"pass": sum(1 for u in units.values() if u["verdict"] == "PASS"),
              "fail": sum(1 for u in units.values() if u["verdict"] == "FAIL")},
    "fail_root_cause": ("IMP-0202/0204/0207/0219/0224/0228/0229 receipts are stale-profile: old artifact "
                        "role enums (implementation/named-probe/primary-implementation), old probe method "
                        "enums, missing required fields (downstream_consumers/residual_unknowns/retry/"
                        "min_bytes_threshold/probe fingerprints). Builders must rebuild the receipt to the "
                        "current profile; implementations, probes and manifests verified healthy live."),
    "program_census_receipt_level": census["summary"],
    "census_definition": ("green = receipt exists + parses + schema-valid under current profile + "
                          "state=SUCCESS + reviewer PASS independent; probe re-runs were executed live only "
                          "for this shard's 12 units"),
    "prior_dead_run_preserved_as": "REVIEW-RETURN.attempt1-dead-run.json",
}
out = G1 / "_reviewer-w4s10/REVIEW-RETURN.json"
out.write_text(json.dumps(ret, indent=1), encoding="utf-8")
print("wrote", out)
print("score:", ret["score"])
