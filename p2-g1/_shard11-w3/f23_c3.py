receipt["residual_unknowns"] = [
    {
        "claim": ("git-crypt itself is absent in the fixture path; isolation and teardown are "
                  "proven with git worktree indexes, git diff --cached --name-only and byte "
                  "digests, not with git-crypt filters."),
        "settling_experiment": ("Re-run measure_disjoint_indexes on a host with git-crypt "
                                "installed and compare the staged-set output."),
        "verdict": "NOT-CHECKED",
    }
]
receipt["retry"] = {"count": 0, "policy": "two strikes then pivot"}
receipt["min_bytes_threshold"] = 128
receipt["manifest_registration"] = {
    "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
    "manifest_path": "command-center/p2-wave/probes/IMP-0223/UNIT-ARTIFACT-MANIFEST.json",
    "registered": True,
}
receipt["timestamps"] = {"started_at": "2026-08-25T00:59:22Z", "ended_at": NOW,
                         "repaired_at": NOW}
receipt["notes"] = (
    "G-1 for IMP-0223: live named probes re-run the provisioner against throwaway git repos. "
    "SUCCESS:IMP-0223 is the catalog sentinel; it is NOT self-declared while state=BLOCKED. "
    "cloud ok=true is not delivery. Did not run global unit_manifest.py --write. "
    "Builder shard11 wave3 resume 2026-10-26: the prior probe directory was lost mid-flight "
    "(host session death) and the module had been rewritten by other work (git-crypt doctor), "
    "which replaced the reviewed provision/teardown semantics with tautological or hardcoded "
    "measurement code. Both defects were repaired with computed implementations; probes were "
    "rebuilt and re-run live; the 2026-08-25 reviewer closure is superseded - see "
    "prior_closure_superseded. Awaiting independent review to close."
)
assert "SUCCESS:IMP-0223" in json.dumps(receipt)
rec_path = REPO / "command-center/receipts/IMP-0223.json"
rec_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
