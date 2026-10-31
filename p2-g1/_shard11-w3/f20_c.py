rec["notes"] = (
    "G-1 for IMP-0207: live named probes exit 0, receipt state=SUCCESS, per-unit manifest row. "
    "Did not run global unit_manifest.py --write. "
    "Builder shard11 wave3 resume 2026-10-26: the prior probe directory was lost mid-flight "
    "(host session death) and the artifact rows here carried hashes of an earlier packs.py "
    "draft (13798B) no longer on disk. Probes and fixtures were rebuilt from the documented "
    "commands and re-run live against the current packs.py and semver.py (both unchanged on "
    "disk since 2026-10-24 08:48). Every claim the independent reviewer PASSed re-verified "
    "live, so the closure is kept. scenario.py was not rebuilt (no probe consumes it); its "
    "stale artifact row was dropped."
)
assert "SUCCESS:IMP-0207" in json.dumps(rec)
rec_path.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")

# ---- SUBAGENT-RETURN ----
sha, n = digest(rec_path)
ret = {
    "id": UID, "unit_id": UID, "status": "DELIVERED", "state": "DELIVERED",
    "receipt_state": "SUCCESS",
    "output_path": "command-center/receipts/IMP-0207.json",
    "output_schema": "command-center/schema/receipt.schema.json",
    "sentinel": "SUCCESS:IMP-0207",
    "manifest_path": "command-center/p2-wave/probes/" + UID + "/UNIT-ARTIFACT-MANIFEST.json",
    "registered": True, "cloud_ok": False, "failure_classification": [],
    "reviewer": rec.get("reviewer"),
    "primary_artifact": {"path": "command-center/receipts/IMP-0207.json",
                         "bytes": n, "sha256": sha},
    "artifacts": artifacts,
    "named_probes": named_probes,
    "notes": ("Builder shard11 wave3 resume 2026-10-26: probe dir was absent (prior builder "
              "died mid-flight); probes and fixtures rebuilt from the receipt documented "
              "commands and re-run live. Implementation untouched; reviewer closure kept "
              "because its claims re-verified live."),
    "ts": NOW,
}
(PROBE_DIR / "SUBAGENT-RETURN.json").write_text(
    json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

# ---- manifest ----
rows = [row("command-center/receipts/IMP-0207.json", "primary")] + artifacts
man = {"unit_id": UID, "artifacts": rows, "generated": NOW,
       "derivation": "shard11-w3 builder resume (matches _measure_one_delivered.py hashing)"}
(PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json").write_text(
    json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("finalized IMP-0207: receipt sha " + sha[:12] + " bytes " + str(n))
