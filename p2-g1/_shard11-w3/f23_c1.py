
receipt["evidence"] = [
    {
        "anchor": "tools/gitcrypt-worktree/gitcrypt_worktree.py:provision_worktree + measure_disjoint_indexes",
        "claim": ("Two concurrent mutating units provisioned on their own branches produce "
                  "disjoint staged sets (computed set intersection empty) and never share a git "
                  "index (distinct gitdirs, index file bytes differ). The shared-index control "
                  "fires: the same two unit paths on ONE checkout with a broad git add -A stage "
                  "both - the contamination mode isolated provisioning prevents."),
        "confidence": "almost-certain",
        "probes": [
            {"command": raws["probe1"][1], "exit_code": raws["probe1"][0],
             "method": "command", "raw_output": raws["probe1"][2], "role": "source"},
            {"command": "staged_a & staged_b == empty; gitdir_a != gitdir_b; "
                        "shared broad-add stages both paths",
             "exit_code": 0, "method": "computed-set-intersection", "role": "verifier"},
        ],
        "verdict": "CONFIRMED",
    },
    {
        "anchor": "tools/gitcrypt-worktree/gitcrypt_worktree.py:teardown_worktree + measure_teardown_both_states",
        "claim": ("Teardown refuses when any live byte or index-referenced path is not proven "
                  "preserved in the harvest (reason=unpreserved-content, worktree stays on "
                  "disk) and deletes only after a byte-level harvest match "
                  "(reason=content-proven). Commit ancestry is never consulted: on the "
                  "squash-merge state the branch reports AHEAD (ahead_count=1, not an ancestor "
                  "despite the content being carried) and the known-broken naive ancestry "
                  "mutant authorizes deletion while the content gate refuses - measured, not "
                  "asserted."),
        "confidence": "almost-certain",
        "probes": [
            {"command": raws["probe2"][1], "exit_code": raws["probe2"][0],
             "method": "command", "raw_output": raws["probe2"][2], "role": "source"},
            {"command": "refused(unharvested-remainder); mutant-authorizes and gate-refuses "
                        "on same squash state; deleted(harvest-matched)",
             "exit_code": 0, "method": "both-states", "role": "verifier"},
        ],
        "verdict": "CONFIRMED",
    },
]
receipt["evidence_computed"] = {
    "disjoint_indexes": comp1,
    "teardown_both_states": comp2,
}
