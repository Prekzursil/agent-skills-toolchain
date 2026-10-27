

def naive_ancestry_authorizes(repo, branch):
    """KNOWN-BROKEN control (measured, never used for authorization).

    The naive mutant reads "branch reports AHEAD of integration" - exactly
    what a squash-merged branch shows, since its unique commit is by
    construction not an ancestor of the squash commit - as "the PR carried
    the work, delete is safe". On a shard with an uncommitted remainder this
    authorizes deletion of unique content. Returned so probes can measure the
    mutant verdict on the same state the content gate refuses.
    """
    ahead = int(_git(["rev-list", "--count", f"HEAD..{branch}"],
                     cwd=str(repo)).stdout.strip() or "0")
    rc, _out, _err = run_git(["merge-base", "--is-ancestor", branch, "HEAD"],
                             cwd=str(repo))
    merged = rc == 0
    return {
        "authorize": ahead > 0 or merged,
        "ahead_count": ahead,
        "reports_ahead": ahead > 0,
        "merged": merged,
    }
