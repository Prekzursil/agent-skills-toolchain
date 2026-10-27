
# ---- SUBAGENT-RETURN (builder-side delivered, receipt BLOCKED pending review) ----
sha, n = digest(REPO / "command-center/receipts/IMP-0223.json")
ret = {
    "id": UID, "unit_id": UID, "status": "DELIVERED", "state": "BLOCKED",
    "receipt_state": "BLOCKED",
    "output_path": "command-center/receipts/IMP-0223.json",
    "output_schema": "command-center/schema/receipt.schema.json",
    "sentinel": "SUCCESS:IMP-0223",
    "manifest_path": "command-center/p2-wave/probes/" + UID + "/UNIT-ARTIFACT-MANIFEST.json",
    "registered": True, "cloud_ok": False,
    "failure_classification": ["reviewer-absent"],
    "reviewer": None,
    "primary_artifact": {"path": "command-center/receipts/IMP-0223.json",
                         "bytes": n, "sha256": sha},
    "artifacts": artifacts,
    "named_probes": named_probes,
    "notes": ("Builder shard11 wave3 resume 2026-10-26: probe dir was absent and the module "
              "measure code was degraded (hardcoded squash verdict, tautological contamination "
              "control) after an unrelated rewrite. Repaired provision/teardown with computed "
              "implementations, rebuilt probes, re-ran live. Receipt BLOCKED reviewer-absent: "
              "the 2026-08-25 independent closure covered a superseded module version."),
    "ts": NOW,
}
(PROBE_DIR / "SUBAGENT-RETURN.json").write_text(
    json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

# ---- manifest ----
rows = [row("command-center/receipts/IMP-0223.json", "primary")] + artifacts
man = {"unit_id": UID, "artifacts": rows, "generated": NOW,
       "derivation": "shard11-w3 builder resume (matches _measure_one_delivered.py hashing)"}
(PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json").write_text(
    json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("finalized IMP-0223: receipt sha " + sha[:12] + " bytes " + str(n))
