# Commit provenance for LANE CASUALTY, build round 1

Recorded because the attribution is misleading and a future reader would otherwise be unable
to find this lane's work in history.

> ## ROUND-2 CORRECTION (audit-confirmed): the ATTRIBUTION below is NOT-CHECKED
>
> This file originally asserted that *"a **sibling agent** committed the whole index"*. **REFUTED
> as an attribution.** Every commit in this repo shares one author identity, so git cannot
> distinguish "a sibling committed our staged index" from "this lane committed a dirty index".
> The refuted wording is left in place below rather than edited away, because deleting it would
> hide the correction.
>
> **CONFIRMED, and unchanged:** `772159ce` is a whole-index commit carrying **31 casualty files
> plus 35 foreign paths** (`.agents/skills/*`, `skills/*`, `scripts/claude-science/*`,
> `commands/*`, `command-center/build/*`), and both lanes' commit-message files landed inside it
> together. Nothing was lost; blob parity is verified below. **Who ran it is unknown, in either
> direction.** *Settling experiment:* correlate the commit's timestamp against each lane's
> transcript tool-call timestamps — or give each lane its own worktree so the question cannot
> arise, which is the recommendation at the foot of this file either way.

## What happened

This lane staged only its own paths (`git add -- command-center/casualty/`) and then attempted
a pathspec-scoped commit. Between the stage and the commit, a **sibling agent committed the
whole index** *(attribution REFUTED in round 2 — see the correction above; the whole-index commit
itself is confirmed)*, sweeping this lane's staged files into its own commit:

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

*(Those are the round-1 byte counts. The round-2 receipt patch changed both files; current sizes
and the re-verified digests are in `LANE-CASUALTY-ROUND2.md`.)*

> **ROUND-2 CORRECTION (audit-confirmed).** The sentence that used to follow — *"So a reviewer
> cloning this repo reproduces both declared digests … closes the no-fresh-clone-verification
> gap"* — is **REFUTED as written: no clone was made.** With a clean working tree, blob ==
> worktree by construction, so the run above proves the *stored blob* reproduces the digests and
> says nothing about a clone. Round 2 implemented the real check:
> `python command-center/casualty/verify_blob_parity.py --fresh-clone` clones the repo into a
> throwaway directory and recomputes each digest from the clone's object store **and** from the
> clone's checked-out file — the second being the one that can differ, since a checkout applies
> EOL conversion. Result recorded in `LANE-CASUALTY-ROUND2.md` §R2-D.

## Recommendation to the orchestrator

Give each lane its own git worktree, or serialise commits behind a lock. Pathspec-scoped commits
protect a lane from *staging* a sibling's files, but nothing protects a lane's staged files from a
sibling's commit.
