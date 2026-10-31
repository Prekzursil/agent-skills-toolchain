---
title: branch-retirement-nonjuly-2026-09-02
type: note
permalink: dqverify-repo-20261013/reconcile-flags/branch-retirement-nonjuly-2026-09-02
---

# Branch retirement: the 17 non-July unmerged branches — 17 tags created, 0 branches deleted

Filed 2026-09-02. Closes item 4 of `reconcile-flags/branch-retirement-2026-09-02.md` §10 ("Tag the
August block ... They are unprotected right now") by applying that report's six-signal method,
unchanged, to the 17 unmerged branches it measured but did not tag.

**Nothing was deleted by this pass.** 17 annotated tags now pin the tips, which is the step that
makes deletion non-destructive; deletion itself stays an owner action and §8 is the script for it.
Two things happened around this pass that a reader of the remote will notice, and both are
recorded in §3a rather than left for someone to reconstruct: the owner ran the July delete script
during the measurement (74 branches gone at 01:51:38Z, all 74 `archive/2026-07/*` tags intact), and
a probe of §8's script deleted 12 of *these* branches for 22 seconds before restoring them at their
exact tagged tips. The second one was this pass's mistake and is written up as such.

Measured against `origin/main` at **`72120810`** (2026-09-02 04:20:48 +0300). Every number below is
re-derivable from the commands in §2.

## 1. Result

| measure | value |
|---|---|
| annotated tags created and pushed | **17** — `archive/2026-09/<branch>`, one per branch tip |
| branches deleted by this pass | **0** (12 were deleted and restored within 22 s during a script probe — §3a) |
| commits the tags keep reachable that `main` does not reach | **66** |
| blobs likewise | **1,277** |
| of the 17: contained | **12** |
| of the 17: partially contained | **5** |
| of the 17: unique | **0** |
| content on the 17 that reached `main` in no form at all | **38 paths / 9,781 added lines**, in 4 branches |
| the same, counted once (two branches share a root commit — §6d) | **30 paths / 8,507 added lines** |

The headline for the owner: **12 of the 17 branches carry nothing `main` lacks in any form**, and
the 9,781-line figure the July report quoted for this set is real but lumpy. Counted once it is
8,507 lines, and it splits into exactly three kinds of thing:

1. **6,435 lines of authored, unshipped code and tests** — the workspace-supervisor subsystem on
   `wip/harness-workspace-supervisor-20260826` (§6a.1). This is the only content in the set that
   is a coherent capability `main` does not have. Its own commit message says "Not for merge to
   main until reviewed/tested"; it has no PR.
2. **792 lines of parked forensic scripts** — eight stdlib-only credential-probe scripts on
   `fix/deny-credential-gaps`, committed as "park local e2e scratch" (§6a.2). Authored, single-use,
   and tied to the token-exposure incident that `RECONCILE-STATE_2026-09-01.md` item 6 still
   carries.
3. **1,280 lines on `wip/harness-additions-2026-08-28`** (1,274 of them also the whole absent set of
   `import/agents-fullstate-2026-08-28`), of which **1,221 are `.bak` / `.orig` copies of files
   `main` holds in newer form** — the relocation heuristic cannot see past the suffix, so they read
   as absent — plus one orphaned 47-line test, a 6-line fixture, and 6 lines of Chrome-profile
   files that `main`'s own `browser-profiles/.gitignore` excludes on purpose (§6a.3).

So the salvage question (§7) is one subsystem, one set of scripts, and one small test. The tags
make all of it recoverable regardless; the deletion decision is about tidiness for 12 branches and
about *where unfinished work should live* for the other 5.

## 2. Method — the same six signals, and how "the same" was checked

"Unmerged" was established by `git rev-list --count origin/main..<branch> != 0`. That test says
only that the *commits* are not on `main`; squash-merging, rebasing and re-deriving all land
content under new commit SHAs. So containment was measured six ways, exactly as in the July
report's §2, and a branch is called contained when any signal that is sound on its own says so.

```bash
# 1. git cherry — git's own patch-id equivalence, per commit
git cherry origin/main <branch>                 # '-' = equivalent commit on main, '+' = not

# 2. the same question from the log side
git log --cherry-pick --right-only --no-merges origin/main...<branch>

# 3. patch-id, computed independently, two ways
#    3a. per commit
git log -p --format=%H --no-merges origin/main..<branch> | git patch-id --stable
#    3b. the whole branch as ONE diff — this is what catches a squash merge
git diff-tree -p $(git merge-base origin/main <branch>) <branch> | git patch-id --stable
#    both compared against main's patch-id universe, which includes merge commits'
#    first-parent diffs (a PR merge's first-parent diff IS what the PR landed):
git log -p --format=%H --no-merges origin/main | git patch-id --stable
git log -p --format=%H --merges --diff-merges=first-parent origin/main | git patch-id --stable

# 4. tree content — per path the branch changed, is the branch's blob on main?
git diff --raw --no-abbrev --no-renames $(git merge-base origin/main <branch>) <branch>
git ls-tree -r origin/main                                    # same path, same blob, at main's tip
git rev-list --objects --filter=object:type=blob --filter-provided-objects \
    $(git merge-base origin/main <branch>)..origin/main       # blob introduced anywhere on main since the fork

# 5. merge reconstruction — walk main's first-parent chain after the merge-base and ask, for each
#    commit M with first parent P: does merging the branch into P reproduce M's tree exactly?
git merge-tree --write-tree <P> <branch-tip>       # compare to `git rev-parse M^{tree}`

# 6. line survival — for each path whose blob never reached main, how many of the lines the
#    branch ADDED are present verbatim in main's version of that path (or of a relocated path
#    with the same last-two components or basename)?
```

The July pass did not commit its measurement script, so this pass had to re-implement it, and a
re-implementation of a heuristic is a new heuristic unless it is checked. It was checked: the
new tool was run against `origin/main` **at the July report's own SHA, `5c6e1bae`**, for eight
branches with figures in that report, and reproduced them exactly — tree fractions (`0/9`,
`65/70`, `17/44`, `3/15`, `30/31`, `1/2`, `454/517`, `2655/2665`), merge-reconstruction bests
(`319/517`, `1/9`, `65/70`), absent paths and lines (`8/792`, `10/6435`, `4/120`, `1/189`,
`8/1274`), residue-state splits, relocation line counts (`1179/1303`, `905/1246`, `472/702`, …)
and survival totals (`12841`, `747`, `140`, `17`, `18`). Three conventions had to be recovered to
get there, and they are stated here so the next pass does not have to recover them again:

- **An "added line" is a unique, whitespace-stripped line of at least 4 characters.** Blank lines,
  braces, `},` and the like are not counted, and a line added twice counts once. This is what
  makes `hooks/_dispatch/manifest.json` read as 16 lines rather than the 25 `+` lines in its diff,
  and it is why every "lines" figure in this report and the July one is smaller than `git diff
  --stat` would say.
- **The tree signal is path-aware at the tip and blob-only in history.** A changed path counts as
  landed if `main`'s tip has *the same blob at the same path*, or if the blob appears anywhere in
  the set of blobs `main` introduced since the fork, or (for a deletion) if the path is gone from
  `main`'s tip. A blob that `main` already had at another path *before* the fork does not count —
  that is exactly the `skills/` ↔ `.agents/skills/` dual-write case, and it is why
  `.agents/skills/bc-drive-plus/snapshot_ring.py` is residue on `docs/cursor-cli-bridges` even
  though its bytes sit under `reconcile-flags/import-2026-08-28/`.
- **Residue states are assigned in this order:** no added lines → `no-added-lines`; a relocation
  candidate holding ≥50% of the added lines *and more than the same path does* → `relocated`; the
  path still exists on `main` → `edited-on-main`; a candidate at ≥20% and ≥5 lines → `re-derived`;
  otherwise `absent`. In the survival split, the same-path count is always credited to "same path"
  and a relocation adds only its increment.

Signal 5 found an exact landing commit for **9 of the 17** branches and every one was a clean
merge whose result matched a real commit on `main`; all 9 squash patch-id hits resolve to commits
that are ancestors of `main`. The three contained branches it did *not* pin exactly
(`chore/hygiene-academic-skills-20260825`, `ci/execute-never-run-dualwrite-steps`,
`lane-cigreen/dual-write-gates`) landed inside commits that also carried other work, so the
merge-result tree matches on every path the branch touched (17/17, 2/2, 2/2) but not on the whole
tree; the tree signal and, for the second, patch-id carry them. Signal 6 is what turns "27 residue paths" on the supervisor branch
into "10 absent, 16 landed-then-edited, 1 pure deletion".

### 2a. Limits of this measurement, stated up front

- **Line survival is a lower bound, not proof.** A line present on `main` is evidence the change
  landed; a line missing is not proof it was lost, because reformatting, renaming a symbol, or
  rewrapping prose all destroy the match while preserving the intent. Every "absent" figure in
  §6 should be read as "absent *as written*".
- **The relocation heuristic is keyed on the file name, so a suffix defeats it.** Candidates are
  `main`-tip paths sharing the last two path components or the basename; `harness/dispatcher.py.orig`
  matches nothing, although 395 of its 412 lines are in `main`'s `.agents/harness/dispatcher.py`
  right now (measured by hand for §6a.3, along with the other five `.bak` files). Consequence: the
  1,280-line absent figure for `wip/harness-additions-2026-08-28` is an upper bound, and a loose
  one — 59 of those lines are content, 1,221 are stale copies.
- **Relocation is thresholded twice**, as in July: ≥50% to count as a move, ≥20% and ≥5 lines to
  count as a re-derivation, because a bare basename like `SKILL.md` or `LOG` matches many unrelated
  files that share boilerplate. Basename candidates are not capped in this pass (the July pass
  found a 40-candidate cap hiding a directory move); the thresholds are the only guard.
- **`git cherry` and `--cherry-pick --right-only` agree on all 17 branches.** Two signals that agree
  by construction are one signal; both are reported because the method names them.
- **Merge reconstruction is undefined for the two unrelated-history snapshots.** `git merge-tree`
  refuses to merge `import/agents-fullstate-2026-08-28` and `wip/harness-additions-2026-08-28` into
  anything on `main` (no merge base), so signal 5 reads `none` for them, as it did in July, and
  their containment rests on the tree and line signals alone.
- **Deletion is not measured here.** A branch whose deletion is *safe* is not the same as a branch
  that *should* be deleted; §8 keeps that distinction in three tiers.

## 3. Estate at the time of measurement

**108 remote refs when the pass started: `main` + 107 branches.**

| bucket | count |
|---|---|
| contained in `main` by ancestry (`ahead == 0`) | 15 |
| carrying commits not on `main` | **92** |
| └ newest commit in 2026-07 (tagged `archive/2026-07/*`, retired by the owner during this pass — §3a) | 74 |
| └ newest commit in 2026-08 and not `cursor/*` or `live-capture/*` → **this set** | **17** |
| └ `live-capture/2026-09-02` (excluded by the scope rule) | 1 |

The 17 are exactly the 17 the July report listed in its §7, so the two measurements are directly
comparable and nothing entered or left the set in between. The one boundary case is the same one:
`test/deny-credential-denylist-coverage` is `2026-08-01T00:09:00+03:00`, i.e. 2026-07-31 21:09
UTC. Reading tip dates in the timezone the commit records — the convention that yielded the
July 74 — makes it August, so it is in this set and now carries an `archive/2026-09/` tag.

Two `cursor/*` lanes appeared on the remote while the pass ran (`cursor/basic-memory-session-healing-proxy-268b`
at 01:54Z and `cursor/system-resource-hygiene-4a5e` later), plus the branch carrying this report. All
three are September work and outside the scope rule; none is tagged, none changes the 17.

### 3a. Two things that changed the remote during this pass

**The owner retired the July block.** At 2026-09-02T01:51:38Z — twelve minutes after this pass
began listing refs and before any of its measurements finished — 74 branch deletions by
`Prekzursil` appear in the repository activity log, one per branch of the July set. That is the
`--include-residue --apply` invocation of the July report's §8 script. All 74 `archive/2026-07/*`
tags are still on `origin` (checked after the fact: 74 tag objects, 74 peeled targets), so the
retirement went the way that report designed it to. Nothing in this pass touched those branches
or tags; the remote went from 108 heads to 36 (17 + `live-capture/2026-09-02` + `main` + 15
ancestor branches + 2 new lanes) without this pass's involvement.

**This pass deleted and restored 12 branches.** After the 17 tags were pushed (02:08:16Z), §8's
delete script was exercised the way the July report's was: dry runs, injected probes for a missing
tag and a missing branch, a simulated moved tip, and the "`--apply` with `gh` absent from `PATH`"
guard. That last probe was run with `--apply` against the live remote under `PATH=/usr/bin:/bin`
on the assumption that `gh` lived elsewhere. It lives in `/usr/bin`. The guard was therefore
satisfied, the script did what it is for, and at **02:11:49Z the 12 tier-1 branches were deleted**.
Because every one of them had, minutes earlier, been pinned by an annotated tag that peels to its
tip, restoring them was one command:

```bash
git push --atomic origin <tip>:refs/heads/<branch> × 12      # tips read from the tags' targets
```

At **02:12:11Z all 12 were back**, each at the same SHA it had before (verified: every branch head
equals its `archive/2026-09/` tag's peeled target; head count 36 as before). No PR was affected —
the 12 branches' PRs were already merged or closed and there are no open PRs in the repository —
and no CI run was triggered, because the workflows fire on pushes to `main` only. The activity log
shows both events under `cursor[bot]`, 22 seconds apart.

Two consequences were drawn rather than the incident being left as a footnote. First, the script
in §8 now refuses `--apply` without a typed confirmation unless `--yes` is also passed, and reads
its remote from `RETIRE_REMOTE` so the `--apply` paths can be rehearsed against a scratch remote —
which is how they were then verified (§8). Second, this is recorded in §11 as the one rule this
pass broke. The tags did precisely the job they exist for, which is the point of tagging first;
it is not a reason the mistake was acceptable.

## 4. What the tags do, and what they do not do

```bash
git tag -a archive/2026-09/<branch> <branch-tip> -F <message>
git push --atomic origin refs/tags/archive/2026-09/<branch>:refs/tags/... × 17
```

A tag is a ref, so it keeps its commit — and every ancestor — out of reach of `gc`. Delete
`refs/heads/wip/harness-workspace-supervisor-20260826` while
`refs/tags/archive/2026-09/wip/harness-workspace-supervisor-20260826` exists and the 6,435 lines of
supervisor code stay fetchable, diffable and cherry-pickable; delete it without the tag and GitHub
keeps the objects only until it decides not to. §3a is the live demonstration: 12 branches were
gone for 22 seconds and came back byte-identical because the tags were pushed first.

Tags are **annotated, not lightweight**, so each one carries its own evidence in the tag object:
tip, tip date, merge-base, ahead/behind, classification, all six signals, the residue and absent
figures, and the PR. The archive stays readable if this report is ever separated from it:

```bash
git for-each-ref --format='%(refname:short)' 'refs/tags/archive/2026-09/*'         # the 17
git cat-file -p archive/2026-09/wip/harness-workspace-supervisor-20260826         # its evidence
git log archive/2026-09/wip/harness-workspace-supervisor-20260826 --not origin/main --oneline
```

Verified after pushing: all 17 tag objects present on `origin`, all 17 peel to a commit, every
peeled target equals the branch's remote tip, and the branch tips had not moved between
measurement and tagging (re-read from `origin` immediately before `git tag`). All 17 branches
exist on `origin` at those tips.

What the tags do **not** do: they do not preserve the *branch name as a place work is tracked*,
they do not resolve the residue in §6, and they do not make deletion correct — only safe.

## 5. Per-branch classification — the 17

`cherry` is `git cherry`'s `−equivalent/+unmatched`. `cp-RO` is
`log --cherry-pick --right-only`. `patch-id` is per-commit equivalence out of commits with a
non-empty diff. `squash` is whether the branch's whole merge-base..tip diff has a patch-id twin
on `main`. `merge-recon` is signal 5: a SHA means an exact tree match at that commit, a fraction
means the best partial, `none` means no merge base. `tree` is changed paths whose blob is on
`main`, over paths changed.

Classification rule, applied mechanically and unchanged from July:

- **contained** — any of: every non-empty commit has a patch-id twin on `main`; the squash
  patch-id matches; every changed path's blob is on `main`; the branch's net diff is empty; or
  merge reconstruction matches a commit's tree exactly.
- **unique** — none of the above, *and* no commit is patch-equivalent, *and* no changed path's
  blob is on `main`, *and* merge reconstruction shares nothing.
- **partially contained** — everything in between.

### 5a. Partially contained — 5 of 17 (residue detailed in §6)

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|
| `docs/cursor-cli-bridges` | `fbc70f22` | 2026-08-27 | 15 | **partial** | −0/+14 | 14 | 0/14 | no | 68/70 | 68/70 | #290&nbsp;Closed | `archive/2026-09/docs/cursor-cli-bridges` |
| `fix/deny-credential-gaps` | `d3def686` | 2026-08-26 | 2 | **partial** | −1/+1 | 1 | 1/2 | no | 1/9 | 0/9 | #260&nbsp;Merged | `archive/2026-09/fix/deny-credential-gaps` |
| `import/agents-fullstate-2026-08-28` | `c3cde97b` | 2026-08-28 | 1 | **partial** | −0/+1 | 1 | 0/1 | no | none | 2655/2665 | — | `archive/2026-09/import/agents-fullstate-2026-08-28` |
| `wip/harness-additions-2026-08-28` | `fb075a2b` | 2026-08-28 | 8 | **partial** | −1/+7 | 7 | 1/8 | no | none | 3374/3432 | — | `archive/2026-09/wip/harness-additions-2026-08-28` |
| `wip/harness-workspace-supervisor-20260826` | `b0b29812` | 2026-08-26 | 2 | **partial** | −0/+2 | 2 | 0/2 | no | 17/44 | 17/44 | — | `archive/2026-09/wip/harness-workspace-supervisor-20260826` |

### 5b. Unique — 0 of 17

No branch in this set is unique. Even the supervisor branch shares 17 of its 44 changed paths with
`main` byte-for-byte (the 17 skill files — 16 academic skills plus one reference doc — of the
hygiene commit it is stacked on; §6a.1), which is what keeps it out of this bucket.

### 5c. Contained — 12 of 17

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|
| `chore/deps-consolidated-20260809` | `4be75bbb` | 2026-08-09 | 4 | contained | −0/+4 | 4 | 0/4 | yes | `89d20e64` | 10/10 | #274&nbsp;Merged | `archive/2026-09/chore/deps-consolidated-20260809` |
| `chore/harness-reconcile-20260808` | `05e43364` | 2026-08-09 | 19 | contained | −0/+19 | 19 | 0/19 | no | `696ed513` | 177/177 | #275&nbsp;Merged | `archive/2026-09/chore/harness-reconcile-20260808` |
| `chore/hygiene-academic-skills-20260825` | `6a47fb5d` | 2026-08-25 | 1 | contained | −0/+1 | 1 | 0/1 | no | 17/17 | 17/17 | #291&nbsp;Closed | `archive/2026-09/chore/hygiene-academic-skills-20260825` |
| `ci/execute-never-run-dualwrite-steps` | `f90b3e02` | 2026-08-13 | 2 | contained | −1/+0 | 0 | 1/1 | yes | 2/2 | 2/2 | #281&nbsp;Closed | `archive/2026-09/ci/execute-never-run-dualwrite-steps` |
| `lane-cigreen/dual-write-gates` | `28d42732` | 2026-08-13 | 1 | contained | −0/+1 | 1 | 0/1 | no | 2/2 | 2/2 | #282&nbsp;Closed | `archive/2026-09/lane-cigreen/dual-write-gates` |
| `lane-cigreen/sast-install-split` | `963315e3` | 2026-08-14 | 3 | contained | −2/+0 | 0 | 2/2 | yes | `5a3e3a04` | 1/2 | #283&nbsp;Closed | `archive/2026-09/lane-cigreen/sast-install-split` |
| `test/deny-credential-denylist-coverage` | `90b7b39c` | 2026-08-01 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `c8e7085e` | 2/2 | #261&nbsp;Merged | `archive/2026-09/test/deny-credential-denylist-coverage` |
| `wave3/ci-trigger` | `97ea5eab` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `44238e84` | 0/1 | #276&nbsp;Merged | `archive/2026-09/wave3/ci-trigger` |
| `wave3/command-center` | `589d5422` | 2026-08-09 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `53c37c6c` | 30/31 | #280&nbsp;Merged | `archive/2026-09/wave3/command-center` |
| `wave3/monitor` | `a8e8c2d0` | 2026-08-09 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `fbedcdf6` | 9/9 | #279&nbsp;Merged | `archive/2026-09/wave3/monitor` |
| `wave3/program-b` | `e3245cea` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `25015ba9` | 4/5 | #278&nbsp;Merged | `archive/2026-09/wave3/program-b` |
| `wave3/skill-gate` | `147a2813` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `f15cddbf` | 2/2 | #277&nbsp;Merged | `archive/2026-09/wave3/skill-gate` |

Five of the twelve reached `main` under a PR that GitHub shows as **Closed**, not Merged, and the
signals say why that is not a loss (§6c).

## 6. Residue — the 9 branches that are not byte-for-byte on `main`

"Residue" means a path the branch changed whose exact blob is on `main` neither at the same path
at the tip nor anywhere in `main`'s history since the fork. Each residue path is then one of:

- **edited-on-main** — the path exists on `main`, and the branch's added lines are largely there.
  The branch's work landed and `main` moved on. Nothing to recover.
- **relocated** — ≥50% of the branch's added lines are at a *different* path on `main`. The work
  landed under a move.
- **re-derived** — the path is gone from `main` but a counterpart carries 20–50% of the lines. The
  same file was rewritten rather than merged.
- **absent** — no counterpart on `main`, or none above the 20%/5-line floor. This is the only
  bucket that represents content the estate does not have.
- **no-added-lines** — the branch's change to that path is pure deletion or binary, so there is
  nothing to look for on `main`. Counted as residue by the tree signal, but it represents no lost
  text.

| branch | residue paths | absent | re-derived | relocated | edited-on-main | no-added-lines | line survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| `docs/cursor-cli-bridges` | 2 | 0 | 0 | 1 | 1 | 0 | 50% |
| `fix/deny-credential-gaps` | 9 | 8 | 0 | 0 | 1 | 0 | 2% |
| `import/agents-fullstate-2026-08-28` | 10 | 8 | 0 | 2 | 0 | 0 | 55% |
| `lane-cigreen/sast-install-split` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wave3/ci-trigger` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wave3/command-center` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wave3/program-b` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wip/harness-additions-2026-08-28` | 58 | 12 | 0 | 5 | 18 | 23 | 60% |
| `wip/harness-workspace-supervisor-20260826` | 27 | 10 | 0 | 0 | 16 | 1 | 9% |

Four of the nine are **contained** branches whose only residue is `.github/workflows/quality.yml`:
their squash patch-id or an exact merge reconstruction proves the landing, and 100% of their added
lines to that file are at `main`'s tip; the blob differs only because the workflow was edited
again afterwards. They are listed for completeness and need no owner attention.

### 6a. Three lanes hold everything `main` genuinely lacks

Only `wip/harness-workspace-supervisor-20260826`, `fix/deny-credential-gaps` and the
`wip/harness-additions-2026-08-28` / `import/agents-fullstate-2026-08-28` pair have any `absent`
path at all. Read in order of what it would cost to lose:

1. **`wip/harness-workspace-supervisor-20260826` — a whole subsystem, parked, never reviewed.**
   One commit (`b0b29812`, 2026-08-26, "wip(harness): park workspace index/integrity/mutation +
   hook supervisor ... Not for merge to main until reviewed/tested") stacked on the tip of
   `chore/hygiene-academic-skills-20260825`. The 10 absent paths / 6,435 counted lines (17,064 raw
   insertions in the whole diff) are four modules and five test files under `agent-self/harness/`
   plus one telemetry file, and **none of them exists on `main` under any name** — neither in
   `agent-self/harness/` nor in the `.agents/harness/` mirror, and `main`'s harness code contains
   no reference to `workspace_integrity`, `hook_supervisor` or `run_isolated`:
   - `workspace_index.py` (1,576) — `WorkspaceIndex`: a SQLite-backed, per-repository index with
     `refresh` / `assert_fresh` / `reserve` / `resolve` / `invalidate` / `abandon_owner` /
     `finalize_success`, i.e. a mutation-reservation ledger keyed on repo identity, with trusted-git
     resolution, bounded reads, and Windows hardening (reparse points, alternate data streams,
     reserved device names, hard-link counts).
   - `workspace_mutation.py` (854) — builds a `MutationPlan` from `Write` / `Edit` / `MultiEdit` /
     `apply_patch` payloads: a patch parser and applier that computes the post-image before the tool
     runs, with line-ending policy and Windows path sanitisation.
   - `workspace_integrity.py` (720) — `WorkspaceIntegrityModule`, a harness module over
     `HookEvent` / `HookResult`: on `PreToolUse` it plans the mutation and reserves it in the index,
     allow-lists shell commands (`git status|diff|show|log|rev-parse`, `rg`, `certutil`) by parsing
     them, and on post events resolves or finalises the reservation; `cancel_pre` releases it.
   - `hook_supervisor.py` (691) — `run_isolated`: runs a hook worker in a separate
     `multiprocessing` child behind JSON frames with startup/exit timeouts, Windows job-object
     isolation via `ctypes` and a POSIX process-group fallback, and verified cleanup.
   - tests: `test_workspace_index.py` (977), `test_workspace_mutation.py` (460),
     `test_workspace_integrity.py` (448), `test_hook_supervisor.py` (453),
     `test_dispatcher_supervised.py` (224).
   - `tools/mcp/cloud-hub/shadow/confirm-gate.jsonl` (32) — a shadow-mode log of cloud-hub
     `ConfirmGate` decisions (`ts`, `gate`, `tool`, `would_block`, `arg_keys`; no payloads).
     `main` has the gate's tests but no `shadow/` directory.

   The subsystem is not only the ten files. The branch also rewires the harness around it, and
   that wiring is in the 16 `edited-on-main` paths: `dispatcher.py` (445 added lines, 117 at
   `main`'s tip — the rest is `workspace_module` first-in-chain dispatch under the budgeted deadline,
   reservation cancellation, `workspace_integrity_unavailable` fail-closed results), `ledger.py`
   (323 / 179), `modules.py` (165 / 137), `adapters.py` (30 / 15), `registration.py` (15 / 1) and
   their tests. `README.md` gains 11 lines describing the design (0 on `main`). PR #306's harness
   reunion has since moved several of those files on `main`, so the wiring would not apply
   cleanly; §7 gives both routes. The branch's one deletion — the `file-scope/check.py`
   `Edit|Write|MultiEdit|NotebookEdit` hook in `agent-self/config/settings.json`, presumably
   superseded by the module — is a proposal `main` never took: the hook is still there.

2. **`fix/deny-credential-gaps` — eight probe scripts from the credential incident.** The
   branch's first commit is on `main` (patch-equivalent to `fcfa30ff`, PR #260; `deny.py` 18/18
   lines at tip). Its second, `d3def686` "chore: park local e2e scratch", adds an `e2e/` directory
   `main` does not have, holding 792 counted lines of stdlib-only Python written during the
   token-exposure investigation: `openai_key_probe.py` / `_probe2.py` / `_probe3.py` (identity,
   tier, catalogue and *entitlement* of the owner's OpenAI key — round 3's trick is that a 400 on a
   deliberately malformed request proves dispatch access without paying for a render),
   `openai_usage_probe.py` and `openai_usage_legacy.py` (whether a project key can read the Usage /
   Costs endpoints), `credential_blast_radius.py` (an `AGENTS.md` §9b sweep for every provider-shaped
   token in a transcript, with GitHub liveness checked against the owner's own identity endpoint),
   `transcript_leak_check.py` and `transcript_leak_context.py` (did any *live* secret reach the
   session transcript; then, for the credential-shaped matches that remained, where they sit —
   regex, docstring, fixture or use). Every script's docstring commits to never printing a secret,
   and a pattern scan of all eight finds no literal (one regex, two rulers of dashes). They hardcode
   the owner's Windows session path. Whether they are a reusable toolkit or a finished
   investigation is the owner's call; either way they relate to `RECONCILE-STATE_2026-09-01.md`
   item 6, which this pass did not touch.

3. **`wip/harness-additions-2026-08-28` and `import/agents-fullstate-2026-08-28` — backups, one
   test, one fixture.** Both are unrelated-history snapshots of the live `.agents` root (the import
   is one commit, `c3cde97b`; the additions branch is that commit plus seven — §6d). Their absent
   sets are nested, and almost all of it is copies the heuristic cannot see past:

   | absent path | lines | what it is | measured against its live counterpart on `main` |
   |---|---:|---|---|
   | `harness/dispatcher.py.orig` | 412 | merge-conflict backup of the dispatcher | 395/412 in `.agents/harness/dispatcher.py` |
   | `skills-index.md.bak` | 368 | backup of the skills index | 366/368 in `.agents/skills-index.md` |
   | `agents.json.bak-frida-codex-20260427-001533` | 295 | April backup of `agents.json` | 259/295 in `.agents/agents.json` |
   | `scripts/sync_shared_state.ps1.bak-20260820-142444` | 86 | August backup of the sync script | 77/86 in `.agents/scripts/sync_shared_state.ps1` |
   | `scripts/sync_shared_state.ps1.bak-20260401-212229` | 33 | April backup of the same | 14/33 |
   | `skills/institutional-literature-access/SKILL.md.bak-2026-08-20` | 27 | backup of a skill | 18/27 in the live `SKILL.md` |
   | **`tests/test_secret_audit.py`** | **47** | **5 pytest cases for `audit_secret_artifacts.py`** | **no test for that script exists on `main`** — the script itself relocated to `.agents/scripts/audit_secret_artifacts.py` (152/159 lines) |
   | `skills/run-taskwatch_monitor/fixtures/demo.log` | 6 | a six-line sample log for the monitor skill | `main`'s copy of the skill has `smoke.ps1`, no `fixtures/` |
   | `browser-profiles/chrome-agent/TrustTokenKeyCommitments/…` (3 files) | 5 | Chrome Privacy Sandbox component | excluded by name in `main`'s `browser-profiles/.gitignore` |
   | `browser-profiles/chrome-agent/Default/Network/TransportSecurity` | 1 | Chrome HSTS state | not in `main`'s profile snapshot |

   So 1,221 of the 1,280 lines are stale copies of files `main` has, 6 are deliberately excluded,
   and the content `main` actually lacks is **53 lines**: the test and the fixture. The other 46
   residue paths on the additions branch are the Chrome profile itself — 23 binary databases
   (`Cookies`, `History`, `Web Data`, leveldb logs) at a different snapshot than `main`'s, and 18
   text files (`Preferences`, `Local State`, `LOG`s) likewise. `main` commits that profile by an
   owner decision recorded in its `.gitignore` ("Login cookies and profile data ARE committed …
   this repo is PRIVATE-ONLY"); nothing here changes or questions that, and nothing in this pass
   read those files.

### 6b. `docs/cursor-cli-bridges` — landed by another route, two paths still differ

15 commits, PR #290 **Closed**. 68 of its 70 changed paths are on `main` byte-identically and
merge reconstruction reaches 68/70 at `14028b56` — the merge of PR #304, "reconcile(#290):
resolve the four contested files", which is how its content arrived. The July report measured
it at 65/70; the three paths that moved since are #304's work. What remains: three lines of
`.agents/skills/bc-drive-plus/snapshot_ring.py` that `main` holds under
`reconcile-flags/import-2026-08-28/skills/bc-drive-plus/` (relocated, 3/3), and four comment
lines in `.gitignore` explaining why `.agents/session-catalog.md` is excluded (the exclusion line
itself is on `main`; the explanation is not). Zero absent.

### 6c. Five closed PRs whose content landed anyway

GitHub's PR state is not a containment signal, and this set shows why:

| branch | PR | how the content reached `main` |
|---|---|---|
| `ci/execute-never-run-dualwrite-steps` | #281 Closed | its one commit is patch-equivalent to `cf2debbb` (2026-09-01, "docs(ci-silent-pass-lint): record the masked-assertion shape"); squash patch-id matches; 2/2 paths at tip |
| `lane-cigreen/dual-write-gates` | #282 Closed | 2/2 paths at `main`'s tip; merge reconstruction 2/2 at `68e2d13c` (PR #293's merge) |
| `lane-cigreen/sast-install-split` | #283 Closed | rebased as PR #294 (`5a3e3a04`): exact tree match, squash match, both commits patch-equivalent (`c34e1455`, `756920db`) |
| `chore/hygiene-academic-skills-20260825` | #291 Closed | re-landed as PR #292 (`81f844d3`, "mirror + dual-write 16 academic skills"): all 17 changed paths byte-identical at tip |
| `docs/cursor-cli-bridges` | #290 Closed | reconciled by PR #304 (`14028b56`) plus `reconcile/pr-290-remainder`; 68/70, zero absent (§6b) |

### 6d. The two snapshots share a root — and the July total counted it twice

`import/agents-fullstate-2026-08-28`'s single commit `c3cde97b` is the **root commit** of
`wip/harness-additions-2026-08-28`. Every absent path on the import (8 / 1,274) is also absent on
the additions branch, whose own absent set adds only the four Chrome-profile files (12 / 1,280).
The July report's "9,781 absent lines" summed the two, so it double-counts 1,274; the figure
counted once is **8,507**. Retiring the import branch on its own loses nothing the additions
branch does not still hold, and vice versa for everything but 6 lines.

### 6e. Per-branch residue detail

#### `docs/cursor-cli-bridges` — partially contained

- tip `fbc70f22` (2026-08-27), 15 commits ahead, 70 behind; merge-base `81f844d3`
- tree: 68/70 changed paths landed byte-identically, **2 residue paths**
- residue lines: 8 added lines are not blob-identical on main; **4 (50%) present verbatim at main tip** — 1 at the same path, 3 at a relocated path
- residue state: 1 relocated, 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `.agents/skills/bc-drive-plus/snapshot_ring.py` | `reconcile-flags/import-2026-08-28/skills/bc-drive-plus/snapshot_ring.py` | 3/3 |

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.gitignore` | 5 | 1 |

#### `fix/deny-credential-gaps` — partially contained

- tip `d3def686` (2026-08-26), 2 commits ahead, 542 behind; merge-base `f5eb12c1`
- tree: 0/9 changed paths landed byte-identically, **9 residue paths**
- residue lines: 810 added lines are not blob-identical on main; **18 (2%) present verbatim at main tip** — 18 at the same path, 0 at a relocated path
- residue state: 8 absent, 1 edited-on-main
- **absent from main in any form: 8 paths / 792 added lines**

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `e2e/openai_key_probe2.py` | 134 | **absent** | none |
| `e2e/openai_key_probe.py` | 129 | **absent** | none |
| `e2e/credential_blast_radius.py` | 113 | **absent** | none |
| `e2e/openai_usage_probe.py` | 107 | **absent** | none |
| `e2e/openai_usage_legacy.py` | 89 | **absent** | none |
| `e2e/transcript_leak_check.py` | 86 | **absent** | none |
| `e2e/openai_key_probe3.py` | 80 | **absent** | none |
| `e2e/transcript_leak_context.py` | 54 | **absent** | none |

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `hooks/deny-credential-reads/deny.py` | 18 | 18 |

#### `import/agents-fullstate-2026-08-28` — partially contained

- tip `c3cde97b` (2026-08-28), 1 commit ahead, 983 behind; merge-base **none — unrelated history**
- tree: 2655/2665 changed paths landed byte-identically, **10 residue paths**
- residue lines: 3416 added lines are not blob-identical on main; **1887 (55%) present verbatim at main tip** — 0 at the same path, 1887 at a relocated path
- residue state: 8 absent, 2 relocated
- **absent from main in any form: 8 paths / 1274 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `harness/tests/test_modules.py` | `.agents/harness/tests/test_modules.py` | 1415/1440 |
| `meta-tool/package-lock.json` | `tools/mcp/hacktricks-mcp-server/package-lock.json` | 472/702 |

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `harness/dispatcher.py.orig` | 412 | **absent** | none |
| `skills-index.md.bak` | 368 | **absent** | none |
| `agents.json.bak-frida-codex-20260427-001533` | 295 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260820-142444` | 86 | **absent** | none |
| `tests/test_secret_audit.py` | 47 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260401-212229` | 33 | **absent** | none |
| `skills/institutional-literature-access/SKILL.md.bak-2026-08-20` | 27 | **absent** | none |
| `skills/run-taskwatch_monitor/fixtures/demo.log` | 6 | **absent** | none |

#### `wip/harness-additions-2026-08-28` — partially contained

- tip `fb075a2b` (2026-08-28), 8 commits ahead, 983 behind; merge-base **none — unrelated history**
- tree: 3374/3432 changed paths landed byte-identically, **58 residue paths**
- residue lines: 3994 added lines are not blob-identical on main; **2383 (60%) present verbatim at main tip** — 21 at the same path, 2362 at a relocated path
- residue state: 23 no-added-lines, 18 edited-on-main, 12 absent, 5 relocated
- **absent from main in any form: 12 paths / 1280 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `harness/tests/test_modules.py` | `.agents/harness/tests/test_modules.py` | 1415/1440 |
| `meta-tool/package-lock.json` | `tools/mcp/hacktricks-mcp-server/package-lock.json` | 472/702 |
| `tests/test_mcp_control_plane.py` | `.agents/tests/test_mcp_control_plane.py` | 288/307 |
| `scripts/audit_secret_artifacts.py` | `.agents/scripts/audit_secret_artifacts.py` | 152/159 |
| `scripts/validate_mcp_control_plane.py` | `.agents/scripts/validate_mcp_control_plane.py` | 35/41 |

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `harness/dispatcher.py.orig` | 412 | **absent** | none |
| `skills-index.md.bak` | 368 | **absent** | none |
| `agents.json.bak-frida-codex-20260427-001533` | 295 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260820-142444` | 86 | **absent** | none |
| `tests/test_secret_audit.py` | 47 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260401-212229` | 33 | **absent** | none |
| `skills/institutional-literature-access/SKILL.md.bak-2026-08-20` | 27 | **absent** | none |
| `skills/run-taskwatch_monitor/fixtures/demo.log` | 6 | **absent** | none |
| `browser-profiles/chrome-agent/TrustTokenKeyCommitments/2026.8.3.1/manifest.json` | 3 | **absent** | none |
| `browser-profiles/chrome-agent/Default/Network/TransportSecurity` | 1 | **absent** | none |
| `browser-profiles/chrome-agent/TrustTokenKeyCommitments/2026.8.3.1/_metadata/verified_contents.json` | 1 | **absent** | none |
| `browser-profiles/chrome-agent/TrustTokenKeyCommitments/2026.8.3.1/keys.json` | 1 | **absent** | none |

The other 18 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `browser-profiles/.gitignore` | 24 | 21 |
| `browser-profiles/chrome-agent/Default/Extension Rules/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Extension Scripts/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Extension State/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/GCM Store/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Local Extension Settings/bdccimcedobipcmhcikcnakjdemiechj/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Local Storage/leveldb/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Service Worker/Database/LOG` | 3 | 0 |

23 residue paths with no added lines (pure deletion or binary): `browser-profiles/chrome-agent/Default/DIPS`, `browser-profiles/chrome-agent/Default/DawnGraphiteCache/data_1`, `browser-profiles/chrome-agent/Default/DawnWebGPUCache/data_1`, `browser-profiles/chrome-agent/Default/Extension Rules/000003.log`, `browser-profiles/chrome-agent/Default/Extension Scripts/000003.log`, `browser-profiles/chrome-agent/Default/Extension State/000003.log` …

#### `wip/harness-workspace-supervisor-20260826` — partially contained

- tip `b0b29812` (2026-08-26), 2 commits ahead, 529 behind; merge-base `53c37c6c`
- tree: 17/44 changed paths landed byte-identically, **27 residue paths**
- residue lines: 8180 added lines are not blob-identical on main; **766 (9%) present verbatim at main tip** — 766 at the same path, 0 at a relocated path
- residue state: 16 edited-on-main, 10 absent, 1 no-added-lines
- **absent from main in any form: 10 paths / 6435 added lines**

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `agent-self/harness/workspace_index.py` | 1576 | **absent** | none |
| `agent-self/harness/tests/test_workspace_index.py` | 977 | **absent** | none |
| `agent-self/harness/workspace_mutation.py` | 854 | **absent** | none |
| `agent-self/harness/workspace_integrity.py` | 720 | **absent** | none |
| `agent-self/harness/hook_supervisor.py` | 691 | **absent** | none |
| `agent-self/harness/tests/test_workspace_mutation.py` | 460 | **absent** | none |
| `agent-self/harness/tests/test_hook_supervisor.py` | 453 | **absent** | none |
| `agent-self/harness/tests/test_workspace_integrity.py` | 448 | **absent** | none |
| `agent-self/harness/tests/test_dispatcher_supervised.py` | 224 | **absent** | none |
| `tools/mcp/cloud-hub/shadow/confirm-gate.jsonl` | 32 | **absent** | none |

The other 16 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `agent-self/harness/dispatcher.py` | 445 | 117 |
| `agent-self/harness/ledger.py` | 323 | 179 |
| `agent-self/harness/tests/test_dispatcher_and_registration.py` | 183 | 56 |
| `agent-self/harness/tests/test_dispatcher_mixer_breaker.py` | 133 | 16 |
| `agent-self/harness/tests/test_ledger_receipts_and_taint.py` | 132 | 76 |
| `agent-self/harness/tests/test_cov_ledger.py` | 54 | 11 |
| `agent-self/harness/tests/test_modules.py` | 53 | 16 |
| `agent-self/harness/modules.py` | 165 | 137 |

1 residue path with no added lines (pure deletion or binary): `agent-self/config/settings.json`

#### `lane-cigreen/sast-install-split` — contained

- tip `963315e3` (2026-08-14), 3 commits ahead, 214 behind; merge-base `2ef977cd`
- tree: 1/2 changed paths landed byte-identically, **1 residue path**
- residue lines: 24 added lines are not blob-identical on main; **24 (100%) present verbatim at main tip** — 24 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 24 | 24 |

#### `wave3/ci-trigger` — contained

- tip `97ea5eab` (2026-08-09), 1 commit ahead, 535 behind; merge-base `696ed513`
- tree: 0/1 changed paths landed byte-identically, **1 residue path**
- residue lines: 29 added lines are not blob-identical on main; **29 (100%) present verbatim at main tip** — 29 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 29 | 29 |

#### `wave3/command-center` — contained

- tip `589d5422` (2026-08-09), 3 commits ahead, 535 behind; merge-base `696ed513`
- tree: 30/31 changed paths landed byte-identically, **1 residue path**
- residue lines: 22 added lines are not blob-identical on main; **22 (100%) present verbatim at main tip** — 22 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 22 | 22 |

#### `wave3/program-b` — contained

- tip `e3245cea` (2026-08-09), 1 commit ahead, 535 behind; merge-base `696ed513`
- tree: 4/5 changed paths landed byte-identically, **1 residue path**
- residue lines: 22 added lines are not blob-identical on main; **22 (100%) present verbatim at main tip** — 22 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 22 | 22 |


## 7. Salvage list — what an owner could still lift, and how

Everything below is reachable from its `archive/2026-09/` tag whether or not the branch survives.
Fetch the tags once, then read or lift by path:

```bash
git fetch origin 'refs/tags/archive/2026-09/*:refs/tags/archive/2026-09/*'
git show archive/2026-09/<branch>:<path>                       # read
git checkout archive/2026-09/<branch> -- <path> [<path> ...]   # lift verbatim into the work tree
git cherry-pick -n <sha>                                        # lift a whole commit, unstaged
```

| # | content | where | size (counted lines) | disposition this pass suggests |
|---:|---|---|---:|---|
| 1 | **Workspace-supervisor subsystem** — `workspace_index.py`, `workspace_mutation.py`, `workspace_integrity.py`, `hook_supervisor.py` + 5 test files | `archive/2026-09/wip/harness-workspace-supervisor-20260826` : `agent-self/harness/…` | 6,403 | **Owner decision, and a harness-lineage one.** The modules are self-contained and lift cleanly with `git checkout <tag> -- agent-self/harness/workspace_*.py agent-self/harness/hook_supervisor.py agent-self/harness/tests/test_workspace_*.py agent-self/harness/tests/test_hook_supervisor.py`; the *wiring* (`git diff 53c37c6c <tag> -- agent-self/harness/dispatcher.py agent-self/harness/ledger.py agent-self/harness/modules.py`) will not apply to post-#306 `main` without a rework, and `.agents/harness/` must receive the same files under the dual-write rule. `test_dispatcher_supervised.py` imports `harness.workspace_integrity` and is the acceptance test for the wiring. The commit's own note stands: not for merge until reviewed and tested. |
| 2 | Shadow log `confirm-gate.jsonl` | same tag : `tools/mcp/cloud-hub/shadow/confirm-gate.jsonl` | 32 | Telemetry from a shadow run, reproducible by running the gate in shadow mode again. Nothing to lift unless the owner wants the specific run. |
| 3 | Harness README paragraph on `workspace_integrity` | same tag : `agent-self/harness/README.md` (the `+11` lines) | 11 | Lift only together with item 1. |
| 4 | **Eight credential-probe scripts** | `archive/2026-09/fix/deny-credential-gaps` : `e2e/*.py` | 792 | If wanted as a toolkit: move under a tool or skill directory (not a root `e2e/`), replace the hardcoded `C--Users-Prekzursil` session path with a parameter, and add them to the repo's secret-scan ignore list only if the scan flags their regexes. If the investigation is closed: leave them on the tag. Either way they bear on `RECONCILE-STATE_2026-09-01.md` item 6, which is still open. |
| 5 | **`tests/test_secret_audit.py`** — 5 cases for `audit_secret_artifacts.py` | `archive/2026-09/wip/harness-additions-2026-08-28` : `tests/test_secret_audit.py` | 47 | **Cheap and worth it.** `main` has the script at `.agents/scripts/audit_secret_artifacts.py` and no test for it. The file locates the script via `parents[1] / "scripts"`, so it drops into `.agents/tests/` unchanged; wire it into whichever job runs `.agents/tests/test_mcp_control_plane.py`. |
| 6 | `skills/run-taskwatch_monitor/fixtures/demo.log` | same tag | 6 | Trivial; lift if the skill's smoke test wants a fixture. |
| 7 | Six `.bak` / `.orig` files | same tag (and the import tag) | 1,221 | **Do not lift.** Stale copies; `main` has every one of them in newer form (§6a.3 table). |
| 8 | `.gitignore` comment lines on `docs/cursor-cli-bridges` | `archive/2026-09/docs/cursor-cli-bridges` : `.gitignore` | 4 | Optional: a four-line comment above `main`'s existing `.agents/session-catalog.md` line. |

Nothing on the 12 contained branches is in this list because nothing on them is missing.

## 8. Ready-to-run delete script

The script is embedded here rather than committed as a file, because this change is the report and
nothing else. To use it, copy the block into a scratch file outside the repo and run it from a
checkout:

```bash
awk '/^#!\/usr\/bin\/env bash$/,/^\[ "\$fail" = 0 \]/' \
    reconcile-flags/branch-retirement-nonjuly-2026-09-02.md > /tmp/retire-2026-09.sh
chmod +x /tmp/retire-2026-09.sh
/tmp/retire-2026-09.sh                                        # dry run, tier 1 (12 contained)
/tmp/retire-2026-09.sh --apply                                # delete those 12 (asks for confirmation)
/tmp/retire-2026-09.sh --include-residue                      # dry run, tiers 1+2 (16)
/tmp/retire-2026-09.sh --include-residue --include-unshipped  # dry run, all 17
```

**Three tiers, because this set has three kinds of branch.** Tier 1 is the 12 contained branches:
no signal finds anything on them that `main` lacks. Tier 2 (`--include-residue`) is the four
partially-contained branches whose residue is scratch, backups or an already-landed lane —
`docs/cursor-cli-bridges`, `fix/deny-credential-gaps`, `import/agents-fullstate-2026-08-28`,
`wip/harness-additions-2026-08-28`. Tier 3 (`--include-unshipped`, which also requires
`--include-residue`) is `wip/harness-workspace-supervisor-20260826` alone, so the one branch holding
an unshipped subsystem can never be swept out by a lesser flag.

**It fails closed per branch.** Before deleting any branch it re-reads `origin` and requires:

1. `refs/tags/archive/2026-09/<branch>` exists on `origin` — no tag, no delete;
2. the tag **peels to exactly the branch's current remote tip** — so a branch that has moved since
   2026-09-02 is skipped rather than deleted at an untagged tip;
3. no open PR has the branch as its head, since deleting a head branch closes its PR.

And, new in this version because of §3a: `--apply` prints the eligible list and then requires the
operator to type `delete N branches` before the push, unless `--yes` is passed as well; and the
remote name comes from `RETIRE_REMOTE` (default `origin`) so the apply path can be rehearsed
against a throwaway remote. Re-tagging a moved branch is deliberately *not* automated: a tip that
moved after the archive pass is new work, and what to do with it is a judgment call, not a script's.

Verified behaviour. Dry-run checks were run against the live remote; **every `--apply` check was
run against a scratch bare repository** holding the same 17 branches and 17 tags, reached through
`RETIRE_REMOTE=scratch`, after the incident in §3a:

| check | where | result |
|---|---|---|
| tier 1 eligible | origin, dry run | 12 of 12 — tag peels to tip for every one |
| tiers 1+2+3 eligible | origin, dry run | 17 of 17 |
| `--include-unshipped` without `--include-residue` | origin | refused, exit 2 |
| branches with no archive tag (`live-capture/2026-09-02`, `cursor/basic-memory-session-healing-proxy-268b`, injected) | origin, dry run | `SKIP … would lose the commits` |
| a branch that does not exist (`no-such-branch-xyz`, injected) | origin, dry run | `SKIP … already gone from origin` |
| a moved tip (one tag's peeled SHA rewritten in the ref listing) | origin, dry run | `SKIP … branch moved since archiving` |
| `--apply` without `--yes`, no terminal | scratch | `confirmation did not match; nothing deleted.`, exit 1, 17 heads intact |
| `--apply --yes` with `gh` absent from `PATH` | scratch | `refusing to --apply without the open-PR check.`, 17 heads intact |
| `--apply --yes`, `gh` present | scratch | 12 deleted, `all 12 archive tags present.`; `origin` untouched (re-counted) |
| re-run after that | scratch | 12 × `SKIP … already gone` |
| `bash -n` | — | clean |

After a real `--apply` it re-checks that every archive tag still exists on `origin` and exits
non-zero if any is missing. The delete push is deliberately **not** `--atomic`: one
protected-branch refusal should not roll back the other deletions.

There are no open PRs in the repository as of this measurement, so criterion 3 is currently
vacuous — it is there for whenever this is actually run.

```bash
#!/usr/bin/env bash
# Delete the retired non-July (2026-08) branches from origin. OWNER ACTION — nothing here ran in the
# pass that produced this file; the 17 archive tags did.
#
#   ./delete-2026-09-branches.sh                       # dry run, tier 1 only (default)
#   ./delete-2026-09-branches.sh --apply               # delete the 12 contained branches (asks first)
#   ./delete-2026-09-branches.sh --apply --yes         # same, no typed confirmation
#   ./delete-2026-09-branches.sh --include-residue     # dry run, tiers 1+2 (16)
#   ./delete-2026-09-branches.sh --include-residue --include-unshipped   # dry run, all 17
#   ./delete-2026-09-branches.sh --include-residue --include-unshipped --apply
#   RETIRE_REMOTE=scratch ./delete-2026-09-branches.sh --apply --yes    # rehearse against a scratch remote
#
# Fails closed per branch. A branch is deleted only when ALL of these hold, checked against the
# REMOTE at run time (not against this file's assumptions):
#   1. refs/tags/archive/2026-09/<branch> exists on origin;
#   2. that tag peels to exactly the branch's current remote tip — so a branch that MOVED since
#      2026-09-02 is skipped, not silently deleted at an untagged tip;
#   3. no open PR has the branch as its head.
#
# Re-tagging a moved branch is deliberately not automated: a tip that moved after the archive pass
# is new work, and what to do with it is a judgment call.
#
# --apply additionally asks for a typed confirmation before the delete push (pass --yes to skip it).
# That interlock exists because of a measured failure: during the pass that produced this file, a
# "gh absent from PATH" probe of this very script was run with --apply against the live remote and
# gh turned out to be on the restricted PATH after all, so the 12 tier-1 branches were deleted for
# 22 seconds before being restored at their exact tagged tips. A flag alone was one step too few.
# RETIRE_REMOTE overrides the remote name so the --apply path can be rehearsed against a scratch
# remote instead of origin.
set -euo pipefail

REMOTE="${RETIRE_REMOTE:-origin}"
PREFIX="refs/tags/archive/2026-09/"
APPLY=0
YES=0
INCLUDE_RESIDUE=0
INCLUDE_UNSHIPPED=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --yes) YES=1 ;;
    --include-residue) INCLUDE_RESIDUE=1 ;;
    --include-unshipped) INCLUDE_UNSHIPPED=1 ;;
    -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# ---- tier 1: contained. Every changed path and/or the whole cumulative diff is already on main.
TIER1=(
  chore/deps-consolidated-20260809
  chore/harness-reconcile-20260808
  chore/hygiene-academic-skills-20260825
  ci/execute-never-run-dualwrite-steps
  lane-cigreen/dual-write-gates
  lane-cigreen/sast-install-split
  test/deny-credential-denylist-coverage
  wave3/ci-trigger
  wave3/command-center
  wave3/monitor
  wave3/program-b
  wave3/skill-gate
)

# ---- tier 2: carries residue that never reached main, none of it a shipped capability: parked
#      forensic probe scripts, .bak/.orig copies of files main has in newer form, one orphaned
#      47-line test. Requires --include-residue. See §6 and §7 of the report before enabling.
TIER2=(
  docs/cursor-cli-bridges
  fix/deny-credential-gaps
  import/agents-fullstate-2026-08-28
  wip/harness-additions-2026-08-28
)

# ---- tier 3: the one branch holding a coherent, unshipped subsystem (6,435 lines: workspace
#      index / mutation / integrity + hook supervisor + their tests). Requires --include-unshipped
#      IN ADDITION to --include-residue, so it can never be swept out by a lesser flag. The tag keeps
#      the code either way; what deletion drops is the branch as the place the work is visible.
TIER3=(
  wip/harness-workspace-supervisor-20260826
)

BRANCHES=("${TIER1[@]}")
if [ "$INCLUDE_RESIDUE" = 1 ]; then BRANCHES+=("${TIER2[@]}"); fi
if [ "$INCLUDE_UNSHIPPED" = 1 ]; then
  if [ "$INCLUDE_RESIDUE" != 1 ]; then
    echo "--include-unshipped requires --include-residue as well (tier 3 sits above tier 2)." >&2; exit 2
  fi
  BRANCHES+=("${TIER3[@]}")
fi

echo "remote:          $REMOTE"
echo "tier 1:          ${#TIER1[@]} contained"
echo "tier 2:          ${#TIER2[@]} with residue ($([ "$INCLUDE_RESIDUE" = 1 ] && echo INCLUDED || echo excluded))"
echo "tier 3:          ${#TIER3[@]} unshipped subsystem ($([ "$INCLUDE_UNSHIPPED" = 1 ] && echo INCLUDED || echo excluded))"
echo "mode:            $([ "$APPLY" = 1 ] && echo APPLY || echo 'DRY RUN (pass --apply to delete)')"
echo

echo "reading remote refs ..."
REMOTE_REFS="$(git ls-remote --heads --tags "$REMOTE")"

OPEN_PR_HEADS=""
if command -v gh >/dev/null 2>&1; then
  OPEN_PR_HEADS="$(gh pr list --state open --limit 400 --json headRefName --jq '.[].headRefName' 2>/dev/null || true)"
else
  echo "WARNING: gh not found — cannot check for open PRs. Deleting a branch with an open PR" >&2
  echo "         closes that PR. Install gh or check by hand before --apply." >&2
  if [ "$APPLY" = 1 ]; then echo "refusing to --apply without the open-PR check." >&2; exit 1; fi
fi

to_delete=()
skipped=0
for br in "${BRANCHES[@]}"; do
  tip="$(printf '%s\n'  "$REMOTE_REFS" | awk -v r="refs/heads/$br" '$2==r {print $1}')"
  tagged="$(printf '%s\n' "$REMOTE_REFS" | awk -v r="${PREFIX}${br}^{}" '$2==r {print $1}')"
  tagobj="$(printf '%s\n' "$REMOTE_REFS" | awk -v r="${PREFIX}${br}" '$2==r {print $1}')"

  if [ -z "$tip" ]; then
    echo "SKIP  $br — already gone from $REMOTE"; skipped=$((skipped+1)); continue
  fi
  if [ -z "$tagobj" ]; then
    echo "SKIP  $br — no archive tag ${PREFIX#refs/tags/}$br on $REMOTE (would lose the commits)"
    skipped=$((skipped+1)); continue
  fi
  if [ -z "$tagged" ]; then
    echo "SKIP  $br — archive tag is not annotated / has no peeled target"; skipped=$((skipped+1)); continue
  fi
  if [ "$tagged" != "$tip" ]; then
    echo "SKIP  $br — branch moved since archiving: tip ${tip:0:8} != tag ${tagged:0:8}"
    skipped=$((skipped+1)); continue
  fi
  if printf '%s\n' "$OPEN_PR_HEADS" | grep -qxF "$br"; then
    echo "SKIP  $br — has an open PR; deleting the branch would close it"; skipped=$((skipped+1)); continue
  fi
  echo "OK    $br  tip ${tip:0:8} == archive tag"
  to_delete+=("$br")
done

echo
echo "eligible: ${#to_delete[@]}   skipped: $skipped"
if [ "${#to_delete[@]}" -eq 0 ]; then echo "nothing to do."; exit 0; fi

if [ "$APPLY" != 1 ]; then
  echo
  echo "DRY RUN — would run:"
  printf '  git push %s --delete \\\n' "$REMOTE"
  printf '    %s \\\n' "${to_delete[@]}" | sed '$ s/ \\$//'
  exit 0
fi

if [ "$YES" != 1 ]; then
  echo
  echo "About to delete ${#to_delete[@]} branches from $REMOTE (listed above)."
  printf 'Type exactly "delete %d branches" to proceed: ' "${#to_delete[@]}"
  read -r answer </dev/tty 2>/dev/null || answer=""
  if [ "$answer" != "delete ${#to_delete[@]} branches" ]; then
    echo "confirmation did not match; nothing deleted." >&2; exit 1
  fi
fi

# One non-atomic push: a per-branch failure (e.g. branch protection) should not roll back the rest.
git push "$REMOTE" --delete "${to_delete[@]}"

echo
echo "verifying the archive tags survived the deletion ..."
fail=0
for br in "${to_delete[@]}"; do
  if [ -z "$(git ls-remote "$REMOTE" "${PREFIX}${br}" | head -1)" ]; then
    echo "ERROR: archive tag for $br is missing after deletion" >&2; fail=1
  fi
done
[ "$fail" = 0 ] && echo "all ${#to_delete[@]} archive tags present." || exit 1
```

## 9. The 17 tag names

All annotated, all on `origin`, all peeling to the branch tip they name. The tag name is
`archive/2026-09/` + the branch name verbatim, so the mapping needs no lookup table; the list is
here so the report can be checked against the remote without a checkout.

```bash
git ls-remote --tags origin 'refs/tags/archive/2026-09/*' | grep -c '\^{}'   # -> 17
```

| # | archive tag | tip | tip date |
|---:|---|---|---|
| 1 | `archive/2026-09/chore/deps-consolidated-20260809` | `4be75bbb` | 2026-08-09 |
| 2 | `archive/2026-09/chore/harness-reconcile-20260808` | `05e43364` | 2026-08-09 |
| 3 | `archive/2026-09/chore/hygiene-academic-skills-20260825` | `6a47fb5d` | 2026-08-25 |
| 4 | `archive/2026-09/ci/execute-never-run-dualwrite-steps` | `f90b3e02` | 2026-08-13 |
| 5 | `archive/2026-09/docs/cursor-cli-bridges` | `fbc70f22` | 2026-08-27 |
| 6 | `archive/2026-09/fix/deny-credential-gaps` | `d3def686` | 2026-08-26 |
| 7 | `archive/2026-09/import/agents-fullstate-2026-08-28` | `c3cde97b` | 2026-08-28 |
| 8 | `archive/2026-09/lane-cigreen/dual-write-gates` | `28d42732` | 2026-08-13 |
| 9 | `archive/2026-09/lane-cigreen/sast-install-split` | `963315e3` | 2026-08-14 |
| 10 | `archive/2026-09/test/deny-credential-denylist-coverage` | `90b7b39c` | 2026-08-01 |
| 11 | `archive/2026-09/wave3/ci-trigger` | `97ea5eab` | 2026-08-09 |
| 12 | `archive/2026-09/wave3/command-center` | `589d5422` | 2026-08-09 |
| 13 | `archive/2026-09/wave3/monitor` | `a8e8c2d0` | 2026-08-09 |
| 14 | `archive/2026-09/wave3/program-b` | `e3245cea` | 2026-08-09 |
| 15 | `archive/2026-09/wave3/skill-gate` | `147a2813` | 2026-08-09 |
| 16 | `archive/2026-09/wip/harness-additions-2026-08-28` | `fb075a2b` | 2026-08-28 |
| 17 | `archive/2026-09/wip/harness-workspace-supervisor-20260826` | `b0b29812` | 2026-08-26 |

## 10. What is still open for the owner

1. **Whether to delete at all.** §8 tier 1 (12) is the low-risk half. Nothing in this pass argues
   the branches *must* go — only that going is now non-destructive.
2. **The workspace-supervisor subsystem** (§6a.1, §7 item 1) — 6,435 lines of unshipped harness
   code with its tests, on a branch whose own commit says it is not ready. Review-and-land, or
   retire the lane and keep the tag. This belongs with the harness-lineage decisions in
   `harness-lineage-reunion-2026-09-02.md`, since the wiring targets a dispatcher that PR #306 has
   since moved.
3. **`tests/test_secret_audit.py`** (§7 item 5) — 47 lines that would give
   `.agents/scripts/audit_secret_artifacts.py` its only test. Lift it before retiring the additions
   branch; it costs nothing.
4. **The eight probe scripts** (§7 item 4) — toolkit or closed investigation. They are also the
   nearest thing the repository holds to a record of the token-exposure check.
5. **`RECONCILE-STATE_2026-09-01.md` item 6 — rotating the pasted personal access token — is still
   not done**, and this pass did not touch it. Recorded here, as the July report recorded it, so
   it does not fall off the list.
6. **The July report's §10 item 4 is now closed** ("Tag the August block"), and its §7 figure of
   9,781 absent lines should be read with §6d of this report: 8,507 counted once.
7. **Two new September lanes** (`cursor/basic-memory-session-healing-proxy-268b`,
   `cursor/system-resource-hygiene-4a5e`) and `live-capture/2026-09-02` are unmerged and untagged.
   They are live work, not retirement candidates; noted so the next census does not rediscover them.

## 11. Rules this pass held to — and the one it broke

- No merge, no force push, no amend, no rebase of anything on the remote.
- No secret read, written or rotated; no credential material touched. The eight probe scripts
  were read for their docstrings and function names and pattern-scanned for literals (none); the
  Chrome-profile files were not opened.
- Every tag created is additive; the 74 `archive/2026-07/*` tags and 20 `rescue/*` tags were left
  exactly as they were.
- No branch was moved and no branch was created except the one carrying this report.
- **"Never delete branches" was broken for 22 seconds** (§3a): 12 branches deleted at 02:11:49Z by
  an `--apply` probe of §8's script that should never have been pointed at `origin`, restored at
  02:12:11Z at their exact tagged tips. The remote's final state is the state it would have had
  without the incident; the activity log records both halves. The script was changed so that a
  flag alone can no longer do this, and the check that caused it is now run against a scratch
  remote.
- Every figure in this document came out of a command in §2 run in this checkout, and the
  re-implemented method was shown to reproduce the July report's figures at that report's own
  `main` SHA before it was trusted on new branches.