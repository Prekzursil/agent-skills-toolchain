# Commit provenance for LANE CASUALTY, build round 1

Recorded because the attribution is misleading and a future reader would otherwise be unable
to find this lane's work in history.

## What happened

This lane staged only its own paths (`git add -- command-center/casualty/`) and then attempted
a pathspec-scoped commit. Between the stage and the commit, a **sibling agent committed the
whole index**, sweeping this lane's staged files into its own commit:

```
772159ce feat(command-center): print WHY a unit is not delivered -- true count is 2 of 2,007, not 9
```

That commit message describes the sibling's work, not this lane's. This lane's own commit then
reported `no changes added to commit`, because there was nothing left to commit.

Two guards did work and are worth keeping:
- `git add -- <lane path>` never added a foreign path.
- The pre-commit check `git diff --cached --name-only | grep -cv '^command-center/casualty/'`
  returned **34**, correctly detecting the sibling's staged files, which is why a blanket
  `git commit` was refused and a pathspec commit was used instead.

The guard that does not exist is one against a *sibling* committing *our* staged index entries.
On a shared worktree, staging is a shared mutable resource: anything staged can be committed by
any concurrent process. This is the documented `parallel-agent-worktree` contamination hazard,
observed live.

## Where the work actually is

All of this lane's round-1 output is in commit **`772159ce`** (verified: `git ls-tree -r HEAD --
command-center/casualty/` lists every file, and `git status --short -- command-center/casualty/`
is clean). Nothing was lost. The narrative that *should* have been the commit message is in
`_r1_commitmsg.txt`, committed alongside, and the full report is `LANE-CASUALTY-REPORT.md`.

## Integrity check after the incident

A sibling's commit could in principle have normalised line endings and broken the receipts'
self-verification. It did not. `verify_blob_parity.py` reads the STORED BLOB with
`git cat-file -p` (not `git archive`, which applies export-time EOL conversion and returns CRLF
on Windows) and recomputes each elided digest:

```
ADV-0021  worktree 171343 B / CRLF 0   blob 171343 B / CRLF 0   blob digest MATCH=True
ADV-0022  worktree 105357 B / CRLF 0   blob 105357 B / CRLF 0   blob digest MATCH=True
```

So a reviewer cloning this repo reproduces both declared digests. That also closes, for these two
artifacts, the gap the six-lens audit flagged program-wide: *no fresh-clone verification exists
anywhere*.

## Recommendation to the orchestrator

Give each lane its own git worktree, or serialise commits behind a lock. Pathspec-scoped commits
protect a lane from *staging* a sibling's files, but nothing protects a lane's staged files from a
sibling's commit.
