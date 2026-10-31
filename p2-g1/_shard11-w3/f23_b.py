
comp1 = computed("probe1")
comp2 = computed("probe2")

old = json.loads((REPO / "command-center/receipts/IMP-0223.json").read_text(encoding="utf-8"))

artifacts = [
    row("tools/gitcrypt-worktree/gitcrypt_worktree.py", "implementation"),
    row("command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py", "probe"),
    row("command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py", "probe"),
]

receipt = {
    "id": UID,
    "unit_id": UID,
    "title": old.get("title", "Implement worktree provisioning and teardown per implementation shard"),
    "spec_anchor": "command-center/WORK-UNIT-CATALOG.json IMP-0223",
    "schema_version": 1,
    "sentinel": "SUCCESS:IMP-0223",
    "state": "BLOCKED",
    "failure": {
        "classification": ["reviewer-absent"],
        "reason": ("Builder-side delivery complete and verified live 2026-10-26 (probes exit 0 "
                   "against throwaway git fixtures, manifest sha matches live bytes), but the "
                   "implementation was materially REPAIRED after the 2026-08-25 independent "
                   "review, so that closure no longer verifies live and was superseded: the "
                   "on-disk module (rewritten 2026-10-24 by the git-crypt doctor work) had lost "
                   "provision/teardown semantics and carried two green-not-live defects - a "
                   "hardcoded squash-case literal dict and a tautological contamination control "
                   "(_staged(x) == _staged(x), true by construction). Awaiting a fresh "
                   "independent review to close."),
    },
    "reviewer": None,
    "prior_closure_superseded": {
        "reviewer_id": old.get("reviewer", {}).get("reviewer_id"),
        "verdict": old.get("reviewer", {}).get("verdict"),
        "independent": old.get("reviewer", {}).get("independent"),
        "ended_at": (old.get("timestamps") or {}).get("ended_at"),
        "why": ("closure covered a module version since rewritten; anchor function teardown "
                "did not exist on disk; claims did not verify live against the current file"),
    },
    "implementation": {
        "module": "tools/gitcrypt-worktree/gitcrypt_worktree.py",
        "provision": "git worktree add -b shard/<unit>/<token>",
        "teardown_authorization": "byte-level harvest comparison only (live files + index paths)",
        "ancestry_authorization": "never",
        "estate_git_mutated": False,
        "note": ("Fixture repos under tempfile only. This estate root has no .git; no git "
                 "add/commit/push/stash/checkout/rebase was run against it. Repair 2026-10-26 "
                 "added provision_worktree / harvest_digest / teardown_worktree and the "
                 "labeled known-broken control naive_ancestry_authorizes; rewrote both measure "
                 "functions so every verdict is computed."),
    },
}
