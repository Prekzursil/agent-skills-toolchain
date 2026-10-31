---
title: branch-retirement-2026-09-02
type: note
permalink: dqverify-repo-20261013/reconcile-flags/branch-retirement-2026-09-02
---

# Branch retirement: the 2026-07 block — 74 tags created, 0 branches deleted

Filed 2026-09-02. Closes measurement on item 5 of `RECONCILE-STATE_2026-09-01.md` §6b
("retire the 2026-07 lanes (74 branches) after confirming each reached `main`").

**Nothing was deleted.** 74 annotated tags now pin the tips, which is the step that makes
deletion non-destructive; deletion itself stays an owner action and §8 is the script for it.
Same discipline as `reconcile-flags/import-2026-08-28/` and `harness-lineage-2026-09-01.md`:
measure, preserve, hand the decision over.

Measured against `origin/main` at **`5c6e1bae`** (2026-09-02 01:54:49 +0300). Every number
below is re-derivable from the commands in §2.

## 1. Result

| measure | value |
|---|---|
| annotated tags created and pushed | **74** — `archive/2026-07/<branch>`, one per July branch tip |
| branches deleted | **0** |
| commits the tags keep reachable that `main` does not reach | **214** |
| blobs likewise | **612** |
| of the 74: contained | **65** |
| of the 74: partially contained | **8** |
| of the 74: unique | **1** |
| content on the 74 that reached `main` in no form at all | **17 paths / 6,344 added lines**, in 3 branches |

The headline for the owner: **71 of the 74 branches carry nothing `main` lacks in any form.** The
other three carry 17 paths / 6,344 lines that reached `main` nowhere — and 5,997 of those lines
are one branch's *generated* prompt artifacts (§6a), not authored code. The tags make all of it
recoverable regardless, so the deletion decision is about tidiness, not about risk.

The 8 "partially contained" branches are not 8 lanes of stranded work. Six of them have **zero**
absent paths: their residue is content that landed on `main` and was then *edited further there*,
which is why the blob no longer matches. §6 separates the two cases per branch.

Two of the 74 tips already carried a `rescue/*` tag from an earlier pass
(`add-databricks-fanout-harness` → `rescue/f08/add-databricks-fanout-harness`,
`fix/derive-167-settlement` → `rescue/c1-land254-settlement`). The new tags are additional, not
replacements; nothing was moved or deleted.

## 2. Method — four independent signals, and why one is not enough

"Unmerged" was established by `git rev-list --count origin/main..<branch> != 0`. That test says
only that the *commits* are not on `main`; it says nothing about whether the *work* is, because
squash-merging, rebasing and re-deriving all land content under new commit SHAs. So containment
was measured four ways, and a branch is called contained when any signal that is sound on its
own says so.

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
git diff --raw --no-renames $(git merge-base origin/main <branch>) <branch>
git ls-tree -r origin/main                                    # at main's tip
git rev-list --objects --filter=object:type=blob --filter-provided-objects \
    $(git merge-base origin/main <branch>)..origin/main       # anywhere in main since the fork
```

Signals 1–3 all rest on patch-id, and **patch-id fails on exactly the cases that matter here**:
it is computed over the diff, so a rebase across a conflicting hunk, a squash that also absorbed
a sibling commit, or a re-derivation onto a moved file all produce a different patch-id for the
same work. That is why `git cherry` reports `+` for 47 of `fin/F05`'s 47 commits (§6.5) even
though 95% of its added lines are sitting on `main` right now. Signal 4 is path-based and so
survives rebases, but breaks under directory moves. Two further signals were added to cover
those gaps:

```bash
# 5. merge reconstruction — walk main's first-parent chain after the merge-base and ask, for each
#    commit M with first parent P: does merging the branch into P reproduce M's tree exactly?
#    A hit identifies the commit that landed the branch, whatever route it took.
git merge-tree --write-tree <P> <branch-tip>       # compare to `git rev-parse M^{tree}`

# 6. line survival — for each path whose blob never reached main, how many of the lines the
#    branch ADDED are present verbatim in main's version of that path (or of a relocated path
#    with the same last-two components, e.g. .../python-testing/SKILL.md)?
```

Signal 5 found the landing commit for **73 of the 91** unmerged branches and every one of those
73 was a clean merge whose result matched a real commit on `main`; all 70 squash patch-id hits
also resolve to commits that are ancestors of `main`. Signal 6 is what turns "22 residue paths"
into the useful statement "0 of them absent, all 22 landed and were then edited further".

### 2a. Limits of this measurement, stated up front

- **Line survival is a lower bound, not proof.** A line present on `main` is evidence the change
  landed; a line missing is not proof it was lost, because reformatting, renaming a symbol, or
  rewrapping prose all destroy the match while preserving the intent. Every "absent" figure in
  §6 should be read as "absent *as written*".
- **Relocation detection is heuristic, and thresholded twice.** Candidates are main-tip paths
  sharing the last two path components, or the basename. A candidate counts as a **relocation**
  only if it carries ≥50% of the branch's added lines for that path, and as a **re-derivation**
  only at ≥20% and ≥5 lines; below that it is discarded and the path reads as `absent`. Both
  floors exist because a bare basename like `SKILL.md`, `CHANGELOG.md` or `live.py` matches many
  unrelated files that share imports and boilerplate — before the second floor was added,
  `tools/monitorcore/monitorcore/live.py` was being credited to `tools/mcpapply/mcpapply/live.py`
  on 2 shared lines out of 36. Consequence: a move this heuristic cannot see reads as `absent`,
  so the absent figures are an upper bound on what is missing.
- **A single false negative was found and fixed during the pass.** Keying relocation candidates
  on basename alone, with a 40-candidate cap, hid the `skills/external/*/SKILL.md` →
  `skills/*/SKILL.md` move and reported 8 paths / 2,212 lines of
  `chore/enshrine-runtime-config` as absent. With last-two-component keying the true figure is
  **1 path / 189 lines**. Any remaining absent figure could be wrong the same way; that is the
  reason the tags were created for all 74 branches rather than only the residue-carrying ones.
- **`git cherry` and `--cherry-pick --right-only` agree on all 91 branches** (each branch's `+`
  count equals its right-only count). Two signals that agree by construction are one signal;
  they are both reported because the task named them, not because they cross-check each other.
- **Deletion is not measured here.** A branch whose deletion is *safe* is not the same as a
  branch that *should* be deleted; §8 tier 2 keeps that distinction.

## 3. Estate at the time of measurement

101 remote refs: `main` + 100 branches.

| bucket | count |
|---|---|
| contained in `main` by ancestry (`ahead == 0`) | 9 |
| carrying commits not on `main` | **91** |
| └ newest commit in 2026-07 → **the retirement set** | **74** |
| └ newest commit in 2026-08 | 17 |

`RECONCILE-STATE_2026-09-01.md` §1 counted **94** carrying unmerged commits. The two figures are
not directly comparable: that count predates the #293–#300 merges (which made
`cursor/cursor-basic-memory-integration-b949` and `cursor/four-surface-grill-decision-queue-6009`,
both in its 94, ancestors of `main`), the 14 deletions its own §6 records, and the branches created
during that pass. What does match exactly, across both measurements, is the **74**.

"Newest commit in 2026-07" uses the tip's committer date **in the timezone the commit records**,
which is the convention `git log` prints and the one §1 of the reconcile state used; it is what
yields exactly 74. It is worth naming because one branch sits on the boundary:
`test/deny-credential-denylist-coverage` is `2026-08-01T00:09:00+03:00`, i.e. 2026-07-31 21:09
UTC. It is treated as **August** — outside the set, not tagged. Reading the same dates in UTC
would move it in and make the set 75.

Also outside the set: two branches that appeared on the remote during this pass
(`cursor/grill-questions-register-rows-573e`, tip 2026-09-01, and `live-capture/2026-09-02`, tip
2026-09-02). Both are September lanes; neither is tagged and neither changes the 74.

## 4. What the tags do, and what they do not do

```bash
git tag -a archive/2026-07/<branch> <branch-tip> -F <message>
git push --atomic origin refs/tags/archive/2026-07/<branch>:refs/tags/... × 74
```

A tag is a ref, so it keeps its commit — and every ancestor — out of reach of `gc`. Delete
`refs/heads/fin/F05` while `refs/tags/archive/2026-07/fin/F05` exists and all 48 commits stay
fetchable, diffable and cherry-pickable; delete it without the tag and GitHub keeps the objects
only until it decides not to. That is the whole of the loss prevention, and it is why the tags
were pushed **before** any delete script was written.

Tags are **annotated, not lightweight**, so each one carries its own evidence in the tag object:
tip, tip date, merge-base, ahead/behind, classification, all six signals, PR, and the residue
figures. The archive stays readable if this report is ever separated from it:

```bash
git for-each-ref --format='%(refname:short)' 'refs/tags/archive/2026-07/*'   # the 74
git cat-file -p archive/2026-07/fin/F05                                      # its evidence
git log archive/2026-07/fin/F05 --not origin/main --oneline                  # its own commits
```

Verified after pushing: all 74 tag objects present on `origin`, all 74 peel to a commit, and
every peeled target equals the branch's remote tip. All 74 branches still exist on `origin`.

What the tags do **not** do: they do not preserve the *branch name as a place work is tracked*,
they do not resolve the residue in §6, and they do not make deletion correct — only safe.

## 5. Per-branch classification — the 74

`cherry` is `git cherry`'s `−equivalent/+unmatched`. `cp-RO` is
`log --cherry-pick --right-only`. `patch-id` is per-commit equivalence out of commits with a
non-empty diff. `squash` is whether the branch's whole merge-base..tip diff has a patch-id twin
on `main`. `merge-recon` is signal 5: a SHA means an exact tree match at that commit, a fraction
means the best partial. `tree` is changed paths whose blob is on `main`, over paths changed.

Classification rule, applied mechanically:

- **contained** — any of: every non-empty commit has a patch-id twin on `main`; the squash
  patch-id matches; every changed path's blob is on `main`; the branch's net diff is empty; or
  merge reconstruction matches a commit's tree exactly.
- **unique** — none of the above, *and* no commit is patch-equivalent, *and* no changed path's
  blob is on `main`, *and* merge reconstruction shares nothing.
- **partially contained** — everything in between.

### 5a. Partially contained — 8 of 74 (residue detailed in §6)

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|
| `add-databricks-fanout-harness` | `f1a009e6` | 2026-07-24 | 5 | **partial** | −0/+5 | 5 | 0/5 | no | 0/40 | 1/40 | — | `archive/2026-07/add-databricks-fanout-harness` |
| `chore/enshrine-runtime-config` | `4bcc65ec` | 2026-07-13 | 15 | **partial** | −0/+15 | 15 | 0/15 | no | 319/517 | 454/517 | #78&nbsp;Merged | `archive/2026-07/chore/enshrine-runtime-config` |
| `chore/sync-from-live-20260725` | `64340915` | 2026-07-25 | 8 | **partial** | −0/+8 | 8 | 0/8 | no | 172/292 | 181/292 | — | `archive/2026-07/chore/sync-from-live-20260725` |
| `feat/monitorcore-codexsource` | `b3127f15` | 2026-07-14 | 2 | **partial** | −0/+2 | 2 | 0/2 | no | 3/15 | 3/15 | #83&nbsp;Closed | `archive/2026-07/feat/monitorcore-codexsource` |
| `fin/F05` | `8b709251` | 2026-07-30 | 48 | **partial** | −0/+47 | 47 | 0/47 | no | 203/216 | 194/216 | #257&nbsp;Merged | `archive/2026-07/fin/F05` |
| `fin/F07` | `bbd90540` | 2026-07-30 | 47 | **partial** | −0/+45 | 45 | 0/45 | no | 204/222 | 194/222 | #256&nbsp;Merged | `archive/2026-07/fin/F07` |
| `fix/ui-audit-dead-button-noise-subtraction` | `1591a858` | 2026-07-31 | 9 | **partial** | −0/+9 | 9 | 0/9 | no | 172/294 | 181/294 | — | `archive/2026-07/fix/ui-audit-dead-button-noise-subtraction` |
| `salvage/mcp-health-sync-20260725` | `64340915` | 2026-07-25 | 8 | **partial** | −0/+8 | 8 | 0/8 | no | 172/292 | 181/292 | — | `archive/2026-07/salvage/mcp-health-sync-20260725` |

### 5b. Unique — 1 of 74

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|
| `fix/ssh-platform-cleanup-20260720` | `bf4eb2a7` | 2026-07-24 | 1 | **UNIQUE** | −0/+1 | 1 | 0/1 | no | 0/1 | 0/1 | — | `archive/2026-07/fix/ssh-platform-cleanup-20260720` |

### 5c. Contained — 65 of 74

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|
| `agent/detector-fix-fp` | `def74263` | 2026-07-24 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `0b1bafb7` | 7/7 | #168&nbsp;Merged | `archive/2026-07/agent/detector-fix-fp` |
| `chore/accounts-store-followups` | `20665bc2` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `30f90ba7` | 2/2 | #202&nbsp;Merged | `archive/2026-07/chore/accounts-store-followups` |
| `chore/retire-brace-expansion-ignore` | `9d8139d5` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `4af9d191` | 1/1 | #194&nbsp;Merged | `archive/2026-07/chore/retire-brace-expansion-ignore` |
| `chore/statusline-gotchas-and-goal-short-20260724` | `ace747b1` | 2026-07-24 | 4 | contained | −0/+4 | 4 | 0/4 | yes | `8a61d931` | 3/3 | #177&nbsp;Merged | `archive/2026-07/chore/statusline-gotchas-and-goal-short-20260724` |
| `ci/gate-cloud-hub-full` | `eaa42fc2` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `3f11802a` | 3/3 | #217&nbsp;Merged | `archive/2026-07/ci/gate-cloud-hub-full` |
| `ci/unignore-wave3` | `cefff8db` | 2026-07-25 | 2 | contained | −2/+0 | 0 | 2/2 | no | `faa3b003` | 2/2 | #215&nbsp;Merged | `archive/2026-07/ci/unignore-wave3` |
| `ci/wire-harness-suites` | `5d4ee9d9` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `8874dea8` | 1/1 | #207&nbsp;Merged | `archive/2026-07/ci/wire-harness-suites` |
| `ci/wire-hooks-regression-harness` | `defc7364` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `736b1321` | 1/1 | #208&nbsp;Merged | `archive/2026-07/ci/wire-hooks-regression-harness` |
| `ci/wire-mcp-hub-suites` | `4135283a` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `e11d6381` | 1/1 | #213&nbsp;Merged | `archive/2026-07/ci/wire-mcp-hub-suites` |
| `cursor/setup-dev-environment-1fd0` | `69172393` | 2026-07-27 | 2 | contained | −1/+0 | 0 | 1/1 | yes | `fbf77e5f` | 1/1 | #189&nbsp;Merged | `archive/2026-07/cursor/setup-dev-environment-1fd0` |
| `data/harness-sota-corpus-2026-07-19` | `93e09f6b` | 2026-07-19 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `9d703be5` | 611/611 | #118&nbsp;Merged | `archive/2026-07/data/harness-sota-corpus-2026-07-19` |
| `docs/ci-coverage-gap-report` | `9b211603` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `60939839` | 1/1 | #204&nbsp;Merged | `archive/2026-07/docs/ci-coverage-gap-report` |
| `docs/fb-graph-cooldown-relanded` | `7da5fddf` | 2026-07-19 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `a01fd444` | 2/2 | #116&nbsp;Merged | `archive/2026-07/docs/fb-graph-cooldown-relanded` |
| `feat/aws-cloud-hub` | `303fdd64` | 2026-07-25 | 2 | contained | −1/+0 | 0 | 1/1 | yes | `99da1955` | 4/4 | #190&nbsp;Merged | `archive/2026-07/feat/aws-cloud-hub` |
| `feat/browser-rail` | `dfa16817` | 2026-07-24 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `700b47c9` | 16/18 | #163&nbsp;Merged | `archive/2026-07/feat/browser-rail` |
| `feat/claim-verify-gate` | `ab7aa065` | 2026-07-24 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `d34b74a7` | 6/7 | #161&nbsp;Merged | `archive/2026-07/feat/claim-verify-gate` |
| `feat/closed-batch-config-editor` | `e64ae329` | 2026-07-24 | 3 | contained | −0/+2 | 2 | 0/2 | yes | `d262fdf1` | 5/5 | #162&nbsp;Merged | `archive/2026-07/feat/closed-batch-config-editor` |
| `feat/fb-instagram-parity` | `f81f17d5` | 2026-07-19 | 2 | contained | −2/+0 | 0 | 2/2 | no | none | 9/9 | #114&nbsp;Merged | `archive/2026-07/feat/fb-instagram-parity` |
| `feat/linkedin-mcp-userscope-registration` | `75a550aa` | 2026-07-21 | 3 | contained | −1/+0 | 0 | 1/1 | yes | `cb5dd9c7` | 3/3 | #126&nbsp;Merged | `archive/2026-07/feat/linkedin-mcp-userscope-registration` |
| `feat/mcp-http-host-shared-transport` | `1b07822e` | 2026-07-24 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `c4becde7` | 9/9 | #159&nbsp;Merged | `archive/2026-07/feat/mcp-http-host-shared-transport` |
| `feat/mcp-surface-census` | `6a584461` | 2026-07-24 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `f3b8a586` | 4/4 | #173&nbsp;Merged | `archive/2026-07/feat/mcp-surface-census` |
| `feat/proxy-mcp-mitmproxy` | `4bfc1581` | 2026-07-20 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `0a124a44` | 7/8 | #127&nbsp;Merged | `archive/2026-07/feat/proxy-mcp-mitmproxy` |
| `feat/repo-map-grounding-pack` | `1b250e66` | 2026-07-24 | 2 | contained | −0/+1 | 1 | 0/1 | yes | `a0934f4d` | 5/5 | #166&nbsp;Merged | `archive/2026-07/feat/repo-map-grounding-pack` |
| `feat/search-expansion-rrf-multilingual` | `f4a7c34f` | 2026-07-24 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `55abc6c8` | 11/13 | #165&nbsp;Merged | `archive/2026-07/feat/search-expansion-rrf-multilingual` |
| `feat/social-corpus-extraction-skill` | `43bc9133` | 2026-07-19 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `db62f4ee` | 7/7 | #106&nbsp;Merged | `archive/2026-07/feat/social-corpus-extraction-skill` |
| `feat/stdin-server` | `4325e52e` | 2026-07-24 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `0251caf7` | 5/7 | #174&nbsp;Merged | `archive/2026-07/feat/stdin-server` |
| `feat/tg1-detector-self-test-toolchain` | `9f79cc0a` | 2026-07-24 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `c9b56dab` | 9/9 | #182&nbsp;Merged | `archive/2026-07/feat/tg1-detector-self-test-toolchain` |
| `feat/tg2-mutation-gate-toolchain` | `d34d91af` | 2026-07-24 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `2e2b452d` | 8/8 | #183&nbsp;Merged | `archive/2026-07/feat/tg2-mutation-gate-toolchain` |
| `feat/variant4-increment1-dbx-monitor-20260721` | `3da8adef` | 2026-07-24 | 3 | contained | −0/+2 | 2 | 0/2 | yes | `19ef8595` | 12/12 | #170&nbsp;Merged | `archive/2026-07/feat/variant4-increment1-dbx-monitor-20260721` |
| `feat/w2-a04` | `388389a1` | 2026-07-23 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `59fece61` | 3/3 | #153&nbsp;Merged | `archive/2026-07/feat/w2-a04` |
| `feat/w2-b21` | `5c7d8496` | 2026-07-23 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `c3c06378` | 3/3 | #158&nbsp;Merged | `archive/2026-07/feat/w2-b21` |
| `feat/w2-f02` | `b9f1339d` | 2026-07-23 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `e07fd6eb` | 8/8 | #157&nbsp;Merged | `archive/2026-07/feat/w2-f02` |
| `feat/w2-k04` | `999732c5` | 2026-07-23 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `105ca443` | 2/2 | #154&nbsp;Merged | `archive/2026-07/feat/w2-k04` |
| `feat/w2-m02` | `521cbac6` | 2026-07-24 | 2 | contained | −1/+0 | 0 | 1/1 | yes | `9e4f0e55` | 7/7 | #160&nbsp;Merged | `archive/2026-07/feat/w2-m02` |
| `feat/w2-m20` | `45a53b37` | 2026-07-23 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `79c9bd4c` | 3/3 | #155&nbsp;Merged | `archive/2026-07/feat/w2-m20` |
| `fin/F02` | `f0969cbc` | 2026-07-30 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `2175e9f0` | 7/7 | #253&nbsp;Merged | `archive/2026-07/fin/F02` |
| `fin/F03` | `cfeae5ec` | 2026-07-31 | 3 | contained | −0/+2 | 2 | 0/2 | yes | `f5eb12c1` | 42/43 | #259&nbsp;Merged | `archive/2026-07/fin/F03` |
| `fin/F04` | `ca60e89d` | 2026-07-30 | 4 | contained | −0/+4 | 4 | 0/4 | yes | `f72366f3` | 31/33 | #255&nbsp;Merged | `archive/2026-07/fin/F04` |
| `fin/F06` | `5bce916a` | 2026-07-30 | 2 | contained | −0/+2 | 2 | 0/2 | no | `e2419cdc` | 18/19 | #258&nbsp;Merged | `archive/2026-07/fin/F06` |
| `fin/F09` | `803b5781` | 2026-07-30 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `9dbb1dce` | 3/3 | #252&nbsp;Merged | `archive/2026-07/fin/F09` |
| `fix/accounts-clear-gitcrypt-error` | `212532bf` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `f3486340` | 2/2 | #195&nbsp;Merged | `archive/2026-07/fix/accounts-clear-gitcrypt-error` |
| `fix/agent-self-harness-parity` | `1b89e439` | 2026-07-26 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `0cd20c07` | 2/2 | #226&nbsp;Merged | `archive/2026-07/fix/agent-self-harness-parity` |
| `fix/complete-tg1-detector-self-test` | `30252128` | 2026-07-24 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `7475ee79` | 3/3 | #184&nbsp;Merged | `archive/2026-07/fix/complete-tg1-detector-self-test` |
| `fix/dead-mcp-detector-honours-disabled` | `6cc5feb9` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `58115d68` | 7/7 | #196&nbsp;Merged | `archive/2026-07/fix/dead-mcp-detector-honours-disabled` |
| `fix/derive-167-settlement` | `847c21f7` | 2026-07-31 | 49 | contained | −0/+47 | 47 | 0/47 | yes | `01c9b9a7` | 222/222 | #254&nbsp;Merged | `archive/2026-07/fix/derive-167-settlement` |
| `fix/git-hygiene-repo-truncation-floor` | `f0cbb4d8` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `aa618007` | 2/2 | #199&nbsp;Merged | `archive/2026-07/fix/git-hygiene-repo-truncation-floor` |
| `fix/harness-corpus-control-guard` | `2212f4ca` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `faa3b003` | 2/2 | #216&nbsp;Merged | `archive/2026-07/fix/harness-corpus-control-guard` |
| `fix/hooks-webfetch-sentinel-and-browser-compress` | `5cdc4b00` | 2026-07-24 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `fc492a6e` | 8/8 | #175&nbsp;Merged | `archive/2026-07/fix/hooks-webfetch-sentinel-and-browser-compress` |
| `fix/linkedin-mcp-sdk-cves` | `782c8573` | 2026-07-19 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `26b98692` | 2/2 | #119&nbsp;Merged | `archive/2026-07/fix/linkedin-mcp-sdk-cves` |
| `fix/mcp-health-agentmail-fbmessenger` | `26be01d0` | 2026-07-23 | 10 | contained | −0/+8 | 8 | 0/8 | yes | `900ae141` | 184/184 | #125&nbsp;Merged | `archive/2026-07/fix/mcp-health-agentmail-fbmessenger` |
| `fix/osv-ignore-brace-expansion` | `f87cf6a5` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `964c54e9` | 2/2 | #191&nbsp;Merged | `archive/2026-07/fix/osv-ignore-brace-expansion` |
| `fix/sentinel-status-field-not-payload` | `396a4578` | 2026-07-25 | 4 | contained | −0/+3 | 3 | 0/3 | yes | `080f39f6` | 5/5 | #198&nbsp;Merged | `archive/2026-07/fix/sentinel-status-field-not-payload` |
| `fix/skill-frontmatter-and-grok-pulls` | `1baa7ad5` | 2026-07-24 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `878cd621` | 32/32 | #167&nbsp;Merged | `archive/2026-07/fix/skill-frontmatter-and-grok-pulls` |
| `fix/stubscan-wrapped-comment` | `f4935703` | 2026-07-27 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `17281629` | 2/2 | #230&nbsp;Merged | `archive/2026-07/fix/stubscan-wrapped-comment` |
| `fix/triage-dispatch-manifest-presence` | `228e3849` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `b695b645` | 2/2 | #210&nbsp;Merged | `archive/2026-07/fix/triage-dispatch-manifest-presence` |
| `fix/triage-dispatch-wiring` | `6c2a6b32` | 2026-07-25 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `2a99dd3e` | 1/1 | #212&nbsp;Merged | `archive/2026-07/fix/triage-dispatch-wiring` |
| `fix/triage-golden-standalone` | `c64a46ca` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `18865220` | 1/1 | #209&nbsp;Merged | `archive/2026-07/fix/triage-golden-standalone` |
| `fix/triage-memory-spool-replay` | `340588d0` | 2026-07-25 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `4c96aa18` | 1/1 | #214&nbsp;Merged | `archive/2026-07/fix/triage-memory-spool-replay` |
| `fix/triage-per-edit-check-secrets` | `c91e40f2` | 2026-07-25 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `4df50a6f` | 2/2 | #211&nbsp;Merged | `archive/2026-07/fix/triage-per-edit-check-secrets` |
| `fix/use-vs-mention-result-scanner` | `1fc1e4e7` | 2026-07-23 | 5 | contained | −0/+3 | 3 | 0/3 | yes | `1338ea65` | 4/4 | #128&nbsp;Merged | `archive/2026-07/fix/use-vs-mention-result-scanner` |
| `fix/w2-a04-flaky-descendant` | `9accffa1` | 2026-07-23 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `d4076fb9` | 1/1 | #156&nbsp;Merged | `archive/2026-07/fix/w2-a04-flaky-descendant` |
| `lane/mcp-consolidation` | `a7aedb75` | 2026-07-24 | 2 | contained | −0/+2 | 2 | 0/2 | yes | `6ee64a8c` | 9/9 | #164&nbsp;Merged | `archive/2026-07/lane/mcp-consolidation` |
| `reconcile/harness-drift-wave2` | `6618d4f9` | 2026-07-21 | 9 | contained | −0/+7 | 7 | 0/7 | no | `9513a3bc` | 35/43 | #123&nbsp;Merged | `archive/2026-07/reconcile/harness-drift-wave2` |
| `salvage/codex-scoping-layer` | `77a53ef5` | 2026-07-19 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `c3ef6715` | 19/19 | #107&nbsp;Merged | `archive/2026-07/salvage/codex-scoping-layer` |
| `w2-c16-error-taxonomy` | `318565b1` | 2026-07-24 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `a919578f` | 4/4 | #181&nbsp;Merged | `archive/2026-07/w2-c16-error-taxonomy` |

## 6. Residue — the 9 July branches that are not fully contained

"Residue" means a path the branch changed whose exact blob is on `main` neither at the tip nor
anywhere in `main`'s history since the fork. Each residue path is then one of:

- **edited-on-main** — the path exists on `main`, and the branch's added lines are largely there.
  The branch's work landed and `main` moved on. Nothing to recover.
- **relocated** — ≥50% of the branch's added lines are at a *different* path on `main`. The work
  landed under a move.
- **re-derived** — a counterpart path exists and carries 20–50% of the lines. The same file was
  rewritten rather than merged.
- **absent** — no counterpart on `main`, or none above the 20%/5-line floor. This is the only
  bucket that represents content the estate does not have.
- **no-added-lines** — the branch's change to that path is pure deletion, so there is nothing to
  look for on `main`. Counted as residue by the tree signal, but it represents no lost content.

| branch | residue paths | absent | re-derived | relocated | edited-on-main | line survival |
|---|---:|---:|---:|---:|---:|---:|
| `add-databricks-fanout-harness` | 39 | 12 | 1 | 23 | 0 | 11% |
| `chore/enshrine-runtime-config` | 63 | 1 | 0 | 29 | 33 | 88% |
| `chore/sync-from-live-20260725` | 111 | 0 | 0 | 2 | 108 | 92% |
| `feat/monitorcore-codexsource` | 12 | 4 | 0 | 1 | 7 | 11% |
| `fin/F05` | 22 | 0 | 0 | 1 | 21 | 95% |
| `fin/F07` | 28 | 0 | 0 | 1 | 27 | 95% |
| `fix/ssh-platform-cleanup-20260720` | 1 | 0 | 0 | 0 | 0 | n/a |
| `fix/ui-audit-dead-button-noise-subtraction` | 113 | 0 | 0 | 2 | 110 | 91% |
| `salvage/mcp-health-sync-20260725` | 111 | 0 | 0 | 2 | 108 | 92% |

### 6a. Three lanes hold everything `main` genuinely lacks

Only `add-databricks-fanout-harness`, `chore/enshrine-runtime-config` and
`feat/monitorcore-codexsource` have any `absent` path at all. Read in order of what it would cost
to lose:

1. **`feat/monitorcore-codexsource` — a real feature, half-landed.** `codex_source.py` is on
   `main` at all three of its paths but re-derived (the branch's test file shares 12 of 341
   lines), and the *live-tailing* half — `monitorcore/live.py`, `tests/test_live.py`,
   `tests/fixtures/codex/rollout-sample.jsonl` — exists nowhere on `main`. 120 lines. Its PR #83
   was **closed, not merged**, and the feature was rebuilt later without the tailing path. This is
   the one branch on the list whose residue is a coherent, wanted capability rather than an
   artifact. Worth an owner look before retiring the *lane* (the tag keeps the code either way).
2. **`chore/enshrine-runtime-config` — one orphaned test.** 189 lines,
   `ci/harness/tests/test_stoploop_boundary.py`, against a `ci/harness/` tree that has since moved
   to `agent-self/harness/` and `.agents/harness/` (29 of its paths relocated there, 88% line
   survival overall). The test targets a boundary that may or may not still exist under the new
   layout; that is a question for the harness-lineage decision in
   `harness-lineage-2026-09-01.md`, not for a branch-retirement pass.
3. **`add-databricks-fanout-harness` — 6,035 of the 6,344 lines, and 5,997 of those generated.**
   The tool itself moved wholesale into a skill: 23 paths relocated to
   `.agents/skills/codex-databricks-fanout/scripts/**` (`batch_runner.py` at 205/214 lines,
   `CSIE-DESIGN.md` at 87/100). What did not move is `generated-prompts/` — four
   `final-*-prompt.md` files totalling 5,664 lines plus five `reviewed/*.json` receipt files —
   — which are *outputs* of running the harness, reproducible by running it again. Outside
   `generated-prompts/` the absent set is 3 files and 38 lines (`CHANGELOG.md`, and one line each
   of `README.md` and `conftest.py`), and `test_contract.py` is re-derived at 21/46 lines. Nothing
   here is authored logic that `main` lacks.

### 6b. The other six are already on `main`, then edited

`fin/F05`, `fin/F07`, `chore/sync-from-live-20260725`, `salvage/mcp-health-sync-20260725`,
`fix/ui-audit-dead-button-noise-subtraction` and `fix/ssh-platform-cleanup-20260720` have **zero**
absent paths between them. 91–95% of their added lines are sitting at `main`'s tip right now; the
missing few percent is `main` having been edited *after* their content landed. `git cherry` calls
these branches 100% unmerged (0 of 47 commits equivalent, for `fin/F05`) — an illustration of why
patch-id alone would have produced a badly wrong answer here.

### 6c. `fin/F05` and `fin/F07` reached `main` by an abandoned route — worth recording

Their PRs (#257, #256) were merged, but into merge commits (`002797e2`, `c2267735`) that are
**not ancestors of today's `main`**. That lineage survives only on `origin/fix/derive-167-settlement`
and the pre-existing tag `rescue/c1-land254-settlement`. The content reached `main` a second time
when `fix/derive-167-settlement` was squashed as `01c9b9a7` (PR #254, "PARTIAL: ~117 of 167
findings").

Measured, so this is not inference: `fin/F05`'s own three commits produce cumulative patch-id
`9f583c14…`, byte-identical to the first-parent diff of its own merge commit `002797e2` — and
`002797e2` is an ancestor of `fix/derive-167-settlement`, which is an ancestor of the squash on
`main`. `fin/F07`'s single own commit (`a8186c3c`) reaches `main` the same way; its patch-id
differs from `c2267735`'s because that merge commit absorbed sibling work too.

Consequence for retirement: deleting `fin/F05` and `fin/F07` is safe (tags exist, content is on
`main`), but **deleting `fix/derive-167-settlement` would drop the only branch holding the
`#256`/`#257` merge lineage**. It is in tier 1 below because it is fully contained — 222/222 paths
landed, squash-matched at `01c9b9a7` — and `rescue/c1-land254-settlement` plus
`archive/2026-07/fix/derive-167-settlement` both pin its tip. Noted because the reason it is safe
is the tag, not the merge.

### 6d. `fix/ssh-platform-cleanup-20260720` — the one "unique" branch is a deletion

The only branch where no signal finds anything: 1 commit, 1 file, **69 deletions and no
additions**. It removes sections 8c, 8d and 10 from `rules/common/windows-shell.md` (a heredoc
gotcha, a stale-branch-diff rule, and the apostrophe-quoting rule), presumably as dedup while
canonicalizing 8e/8f — but 8e and 8f are already on `main`, and the three deleted sections are
**still on `main` and exist in no other file there** (checked with `git grep -l` across the whole
tip tree; only `.../workflow-foundry/SKILL.md` and `docs/social/TIKTOK-MCP.md` mention the
apostrophe rule in passing, not the content).

So its uniqueness is a *proposal main never took*, not content main is missing. Retiring the branch
loses nothing but the proposal, and the tag keeps that. If the dedup was in fact wanted, it is a
two-line edit today — not a branch to merge.

#### `add-databricks-fanout-harness` — partially contained

- tip `f1a009e6` (2026-07-24), 5 commits ahead, 602 behind; merge-base `a919578f`
- tree: 1/40 changed paths landed byte-identically, **39 residue paths**
- residue lines: 7184 added lines are not blob-identical on main; **814 (11%) present verbatim at main tip** — 0 at the same path, 814 at a relocated path
- residue state: 23 relocated, 12 absent, 3 no-added-lines, 1 re-derived
- **absent from main in any form: 12 paths / 6035 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `tools/databricks-fanout-harness/node/batch_runner.py` | `.agents/skills/codex-databricks-fanout/scripts/batch_runner.py` | 205/214 |
| `tools/databricks-fanout-harness/harness/lanes/run_E.py` | `.agents/skills/codex-databricks-fanout/scripts/harness/lanes/run_E.py` | 88/126 |
| `tools/databricks-fanout-harness/docs/CSIE-DESIGN.md` | `.agents/skills/codex-databricks-fanout/references/CSIE-DESIGN.md` | 87/100 |
| `tools/databricks-fanout-harness/e2e/watch.py` | `.agents/skills/codex-databricks-fanout/scripts/e2e/watch.py` | 45/89 |
| `tools/databricks-fanout-harness/harness/contract.py` | `.agents/skills/codex-databricks-fanout/scripts/harness/contract.py` | 52/76 |
| `tools/databricks-fanout-harness/harness/lanes/preflight_units.py` | `.agents/skills/codex-databricks-fanout/scripts/harness/lanes/preflight_units.py` | 46/62 |
| `tools/databricks-fanout-harness/e2e/smoke_2unit.py` | `.agents/skills/codex-databricks-fanout/scripts/e2e/smoke_2unit.py` | 31/55 |
| `tools/databricks-fanout-harness/harness/submit.py` | `.agents/skills/codex-databricks-fanout/scripts/harness/submit.py` | 27/46 |

*(+15 more relocations in the same directory move)*

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `tools/databricks-fanout-harness/generated-prompts/final-hacktricks-prompt.md` | 2166 | **absent** | none |
| `tools/databricks-fanout-harness/generated-prompts/final-workflow-prompt.md` | 1835 | **absent** | none |
| `tools/databricks-fanout-harness/generated-prompts/final-cyberstrike-prompt.md` | 1337 | **absent** | none |
| `tools/databricks-fanout-harness/generated-prompts/final-parallel-orchestrator-prompt.md` | 326 | **absent** | none |
| `tools/databricks-fanout-harness/generated-prompts/reviewed/hacktricks.receipts.json` | 119 | **absent** | none |
| `tools/databricks-fanout-harness/generated-prompts/reviewed/cyberstrike.receipts.json` | 72 | **absent** | none |
| `tools/databricks-fanout-harness/generated-prompts/reviewed/workflow.receipts.json` | 62 | **absent** | none |
| `tools/databricks-fanout-harness/generated-prompts/reviewed/_summary.json` | 53 | **absent** | none |
| `tools/databricks-fanout-harness/tests/test_contract.py` | 46 | **re-derived** | `.agents/skills/codex-databricks-fanout/scripts/tests/test_contract.py` (21/46 lines) |
| `tools/databricks-fanout-harness/CHANGELOG.md` | 36 | **absent** | none |

*(+3 more, same shape)*


#### `chore/enshrine-runtime-config` — partially contained

- tip `4bcc65ec` (2026-07-13), 15 commits ahead, 729 behind; merge-base `80a58638`
- tree: 454/517 changed paths landed byte-identically, **63 residue paths**
- residue lines: 14576 added lines are not blob-identical on main; **12841 (88%) present verbatim at main tip** — 5112 at the same path, 7729 at a relocated path
- residue state: 33 edited-on-main, 29 relocated, 1 absent
- **absent from main in any form: 1 paths / 189 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `ci/harness/modules.py` | `agent-self/harness/modules.py` | 1179/1303 |
| `ci/harness/tests/test_modules.py` | `agent-self/harness/tests/test_modules.py` | 905/1246 |
| `ci/harness/install.py` | `.agents/harness/install.py` | 590/627 |
| `skills/external/python-testing/SKILL.md` | `ci/skills-allowlist/python-testing/SKILL.md` | 501/505 |
| `skills/external/python-patterns/SKILL.md` | `.agents/skills/python-patterns/SKILL.md` | 453/453 |
| `ci/harness/dispatcher.py` | `agent-self/harness/dispatcher.py` | 292/383 |
| `ci/harness/tests/test_install_reconciler.py` | `.agents/harness/tests/test_install_reconciler.py` | 365/371 |
| `ci/harness/ledger.py` | `agent-self/harness/ledger.py` | 293/306 |

*(+21 more relocations in the same directory move)*

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `ci/harness/tests/test_stoploop_boundary.py` | 189 | **absent** | none |

The other 33 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `skills/re-triage-preflight/triage.py` | 705 | 586 |
| `skills/microsoft-foundry/foundry-agent/invoke/invoke.md` | 100 | 8 |
| `skills/microsoft-foundry/foundry-agent/invoke/references/session-management.md` | 72 | 0 |
| `skills/microsoft-foundry/foundry-agent/invoke/references/file-operations.md` | 62 | 1 |
| `skills/bc-update-survival/aob_resolver.py` | 708 | 665 |
| `skills/microsoft-foundry/foundry-agent/create/quick-start-hosted.md` | 190 | 148 |

#### `chore/sync-from-live-20260725` — partially contained

- tip `64340915` (2026-07-25), 8 commits ahead, 661 behind; merge-base `26b98692`
- tree: 181/292 changed paths landed byte-identically, **111 residue paths**
- residue lines: 15235 added lines are not blob-identical on main; **14034 (92%) present verbatim at main tip** — 14021 at the same path, 13 at a relocated path
- residue state: 108 edited-on-main, 2 relocated, 1 no-added-lines
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `.agents/skills/create-tooluniverse-skill/assets/skill_template/python_implementation.py` | `.agents/library/skills/tooluniverse-metabolomics/python_implementation.py` | 6/12 |
| `.agents/skills/microsoft-foundry/foundry-agent/create/references/tool-a2a.md` | `.agents/skills/microsoft-foundry/foundry-agent/toolbox/references/tool-a2a.md` | 7/7 |

The other 108 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.agents/skills/re-triage-preflight/triage.py` | 705 | 586 |
| `.agents/skills/cv-studio/scripts/cvstudio.py` | 76 | 3 |
| `tools/crcp/crcp/__main__.py` | 505 | 446 |
| `tools/crcp/crcp/auth_mirror.py` | 489 | 433 |
| `.agents/skills/bc-update-survival/aob_resolver.py` | 708 | 665 |
| `.agents/skills/bc-drive-plus/dispatch_capture.py` | 328 | 288 |

#### `feat/monitorcore-codexsource` — partially contained

- tip `b3127f15` (2026-07-14), 2 commits ahead, 725 behind; merge-base `0d7112de`
- tree: 3/15 changed paths landed byte-identically, **12 residue paths**
- residue lines: 1305 added lines are not blob-identical on main; **140 (11%) present verbatim at main tip** — 139 at the same path, 1 at a relocated path
- residue state: 7 edited-on-main, 4 absent, 1 relocated
- **absent from main in any form: 4 paths / 120 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `tools/monitorcore/tests/fixtures/monitors.toml` | `.agents/skills/monitor-launcher/monitors.toml` | 2/3 |

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `skills/workflow-monitor/monitorcore/live.py` | 36 | **absent** | none |
| `tools/monitorcore/monitorcore/live.py` | 36 | **absent** | none |
| `tools/monitorcore/tests/test_live.py` | 36 | **absent** | none |
| `tools/monitorcore/tests/fixtures/codex/rollout-sample.jsonl` | 12 | **absent** | none |

The other 7 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `skills/workflow-monitor/monitorcore/codex_source.py` | 407 | 58 |
| `tools/monitorcore/monitorcore/codex_source.py` | 407 | 58 |
| `tools/monitorcore/tests/test_codex_source.py` | 341 | 12 |
| `tools/monitorcore/tests/test_monitors.py` | 17 | 5 |
| `skills/monitor-launcher/monitors.toml` | 4 | 2 |
| `skills/workflow-monitor/codex_monitor.py` | 5 | 3 |

#### `fin/F05` — partially contained

- tip `8b709251` (2026-07-30), 48 commits ahead, 514 behind; merge-base `dab44bad`
- tree: 194/216 changed paths landed byte-identically, **22 residue paths**
- residue lines: 1431 added lines are not blob-identical on main; **1353 (95%) present verbatim at main tip** — 1344 at the same path, 9 at a relocated path
- residue state: 21 edited-on-main, 1 relocated
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `rules/common/hooks.md` | `agent-self/config/rules/common/hooks.md` | 9/9 |

The other 21 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `agent-self/config/rules/common/performance.md` | 20 | 0 |
| `hooks/per-edit-check/check.py` | 250 | 235 |
| `rules/README.md` | 46 | 31 |
| `agent-self/config/rules/web/hooks.md` | 36 | 24 |
| `rules/web/hooks.md` | 36 | 24 |
| `tools/crcp/crcp/auth.py` | 4 | 2 |

#### `fin/F07` — partially contained

- tip `bbd90540` (2026-07-30), 47 commits ahead, 514 behind; merge-base `dab44bad`
- tree: 194/222 changed paths landed byte-identically, **28 residue paths**
- residue lines: 1617 added lines are not blob-identical on main; **1534 (95%) present verbatim at main tip** — 1525 at the same path, 9 at a relocated path
- residue state: 27 edited-on-main, 1 relocated
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `rules/common/hooks.md` | `agent-self/config/rules/common/hooks.md` | 9/9 |

The other 27 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `agent-self/config/rules/common/performance.md` | 20 | 0 |
| `hooks/per-edit-check/check.py` | 233 | 218 |
| `rules/README.md` | 46 | 31 |
| `agent-self/config/rules/web/hooks.md` | 36 | 24 |
| `rules/web/hooks.md` | 36 | 24 |
| `tools/crcp/crcp/auth.py` | 4 | 2 |

#### `fix/ssh-platform-cleanup-20260720` — unique

- tip `bf4eb2a7` (2026-07-24), 1 commits ahead, 610 behind; merge-base `fc492a6e`
- tree: 0/1 changed paths landed byte-identically, **1 residue paths**
- residue lines: 0 added lines are not blob-identical on main; **0 (n/a) present verbatim at main tip** — 0 at the same path, 0 at a relocated path
- residue state: 1 no-added-lines
- **absent from main in any form: 0 paths / 0 added lines**


#### `fix/ui-audit-dead-button-noise-subtraction` — partially contained

- tip `1591a858` (2026-07-31), 9 commits ahead, 661 behind; merge-base `26b98692`
- tree: 181/294 changed paths landed byte-identically, **113 residue paths**
- residue lines: 15399 added lines are not blob-identical on main; **14060 (91%) present verbatim at main tip** — 14047 at the same path, 13 at a relocated path
- residue state: 110 edited-on-main, 2 relocated, 1 no-added-lines
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `.agents/skills/create-tooluniverse-skill/assets/skill_template/python_implementation.py` | `.agents/library/skills/tooluniverse-metabolomics/python_implementation.py` | 6/12 |
| `.agents/skills/microsoft-foundry/foundry-agent/create/references/tool-a2a.md` | `.agents/skills/microsoft-foundry/foundry-agent/toolbox/references/tool-a2a.md` | 7/7 |

The other 110 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.agents/skills/re-triage-preflight/triage.py` | 705 | 586 |
| `.agents/skills/cv-studio/scripts/cvstudio.py` | 76 | 3 |
| `.agents/skills/ui-audit/dead_button_crawl.mjs` | 82 | 13 |
| `skills/ui-audit/dead_button_crawl.mjs` | 82 | 13 |
| `tools/crcp/crcp/__main__.py` | 505 | 446 |
| `tools/crcp/crcp/auth_mirror.py` | 489 | 433 |

#### `salvage/mcp-health-sync-20260725` — partially contained

- tip `64340915` (2026-07-25), 8 commits ahead, 661 behind; merge-base `26b98692`
- tree: 181/292 changed paths landed byte-identically, **111 residue paths**
- residue lines: 15235 added lines are not blob-identical on main; **14034 (92%) present verbatim at main tip** — 14021 at the same path, 13 at a relocated path
- residue state: 108 edited-on-main, 2 relocated, 1 no-added-lines
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `.agents/skills/create-tooluniverse-skill/assets/skill_template/python_implementation.py` | `.agents/library/skills/tooluniverse-metabolomics/python_implementation.py` | 6/12 |
| `.agents/skills/microsoft-foundry/foundry-agent/create/references/tool-a2a.md` | `.agents/skills/microsoft-foundry/foundry-agent/toolbox/references/tool-a2a.md` | 7/7 |

The other 108 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.agents/skills/re-triage-preflight/triage.py` | 705 | 586 |
| `.agents/skills/cv-studio/scripts/cvstudio.py` | 76 | 3 |
| `tools/crcp/crcp/__main__.py` | 505 | 446 |
| `tools/crcp/crcp/auth_mirror.py` | 489 | 433 |
| `.agents/skills/bc-update-survival/aob_resolver.py` | 708 | 665 |
| `.agents/skills/bc-drive-plus/dispatch_capture.py` | 328 | 288 |

#### `docs/cursor-cli-bridges` — partially contained  *(not in the 74 — no archive tag created)*

- tip `fbc70f22` (2026-08-27), 15 commits ahead, 37 behind; merge-base `81f844d3`
- tree: 65/70 changed paths landed byte-identically, **5 residue paths**
- residue lines: 68 added lines are not blob-identical on main; **17 (25%) present verbatim at main tip** — 13 at the same path, 4 at a relocated path
- residue state: 3 edited-on-main, 2 relocated
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `.agents/skills/bc-drive-plus/snapshot_ring.py` | `reconcile-flags/import-2026-08-28/skills/bc-drive-plus/snapshot_ring.py` | 3/3 |
| `.agents/skills/mechanistic-ddi-pipeline/SKILL.md` | `reconcile-flags/import-2026-08-28/skills/mechanistic-ddi-pipeline/SKILL.md` | 1/1 |

The other 3 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `scripts/sync-from-live.ps1` | 43 | 0 |
| `.gitignore` | 5 | 1 |
| `hooks/_dispatch/manifest.json` | 16 | 12 |

#### `fix/deny-credential-gaps` — partially contained  *(not in the 74 — no archive tag created)*

- tip `d3def686` (2026-08-26), 2 commits ahead, 509 behind; merge-base `f5eb12c1`
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

The other 1 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `hooks/deny-credential-reads/deny.py` | 18 | 18 |

#### `import/agents-fullstate-2026-08-28` — partially contained  *(not in the 74 — no archive tag created)*

- tip `c3cde97b` (2026-08-28), 1 commits ahead, 950 behind; merge-base **none — unrelated history**
- tree: 2655/2665 changed paths landed byte-identically, **10 residue paths**
- residue lines: 3416 added lines are not blob-identical on main; **1806 (53%) present verbatim at main tip** — 0 at the same path, 1806 at a relocated path
- residue state: 8 absent, 2 relocated
- **absent from main in any form: 8 paths / 1274 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `harness/tests/test_modules.py` | `agent-self/harness/tests/test_modules.py` | 1334/1440 |
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


#### `wip/harness-additions-2026-08-28` — partially contained  *(not in the 74 — no archive tag created)*

- tip `fb075a2b` (2026-08-28), 8 commits ahead, 950 behind; merge-base **none — unrelated history**
- tree: 3374/3432 changed paths landed byte-identically, **58 residue paths**
- residue lines: 3994 added lines are not blob-identical on main; **2302 (58%) present verbatim at main tip** — 21 at the same path, 2281 at a relocated path
- residue state: 23 no-added-lines, 18 edited-on-main, 12 absent, 5 relocated
- **absent from main in any form: 12 paths / 1280 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `harness/tests/test_modules.py` | `agent-self/harness/tests/test_modules.py` | 1334/1440 |
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

*(+2 more, same shape)*

The other 18 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `browser-profiles/.gitignore` | 24 | 21 |
| `browser-profiles/chrome-agent/Default/Extension Rules/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Extension Scripts/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Extension State/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/GCM Store/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Local Extension Settings/bdccimcedobipcmhcikcnakjdemiechj/LOG` | 3 | 0 |

#### `wip/harness-workspace-supervisor-20260826` — partially contained  *(not in the 74 — no archive tag created)*

- tip `b0b29812` (2026-08-26), 2 commits ahead, 496 behind; merge-base `53c37c6c`
- tree: 17/44 changed paths landed byte-identically, **27 residue paths**
- residue lines: 8180 added lines are not blob-identical on main; **747 (9%) present verbatim at main tip** — 288 at the same path, 459 at a relocated path
- residue state: 11 edited-on-main, 10 absent, 5 relocated, 1 no-added-lines
- **absent from main in any form: 10 paths / 6435 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `agent-self/harness/ledger.py` | `.agents/harness/ledger.py` | 179/323 |
| `agent-self/harness/modules.py` | `.agents/harness/modules.py` | 137/165 |
| `agent-self/harness/tests/test_ledger_process_recovery.py` | `.agents/harness/tests/test_ledger_process_recovery.py` | 123/136 |
| `agent-self/harness/tests/test_ledger_receipts_and_taint.py` | `.agents/harness/tests/test_ledger_receipts_and_taint.py` | 76/132 |
| `agent-self/harness/adapters.py` | `.agents/harness/adapters.py` | 27/30 |

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

The other 11 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `agent-self/harness/dispatcher.py` | 445 | 91 |
| `agent-self/harness/tests/test_dispatcher_and_registration.py` | 183 | 56 |
| `agent-self/harness/tests/test_dispatcher_mixer_breaker.py` | 133 | 16 |
| `agent-self/harness/tests/test_cov_ledger.py` | 54 | 8 |
| `agent-self/harness/tests/test_modules.py` | 53 | 16 |
| `agent-self/harness/tests/test_native_events.py` | 28 | 4 |

## 7. Per-branch classification — the 17 unmerged branches outside the set

Measured with the same six signals and listed for completeness. **No archive tag was created for
any of these, and none should be deleted on the basis of this report** — the task scoped tagging
to the 2026-07 block, and these branches carry far more absent residue than the July set does:

| branch | absent paths | absent lines |
|---|---:|---:|
| `wip/harness-workspace-supervisor-20260826` | 10 | **6,435** |
| `wip/harness-additions-2026-08-28` | 12 | 1,280 |
| `import/agents-fullstate-2026-08-28` | 8 | 1,274 |
| `fix/deny-credential-gaps` | 8 | 792 |
| the other 13 | 0 | 0 |

The supervisor branch alone holds a whole subsystem `main` has never seen —
`workspace_index.py` (1,576 lines), `workspace_mutation.py` (854), `workspace_integrity.py` (720),
`hook_supervisor.py` (691) and their three test files. **Tagging the August block is the obvious
next pass, and it matters more than this one did.** It was not done here because it was not asked
for, and because those branches are recent enough that some may still be live work.

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR |
|---|---|---|---:|---|---|---:|---|---|---|---|---|
| `chore/deps-consolidated-20260809` | `4be75bbb` | 2026-08-09 | 4 | contained | −0/+4 | 4 | 0/4 | yes | `89d20e64` | 10/10 | #274&nbsp;Merged |
| `chore/harness-reconcile-20260808` | `05e43364` | 2026-08-09 | 19 | contained | −0/+19 | 19 | 0/19 | no | `696ed513` | 177/177 | #275&nbsp;Merged |
| `chore/hygiene-academic-skills-20260825` | `6a47fb5d` | 2026-08-25 | 1 | contained | −0/+1 | 1 | 0/1 | no | none | 17/17 | #291&nbsp;Closed |
| `ci/execute-never-run-dualwrite-steps` | `f90b3e02` | 2026-08-13 | 2 | contained | −1/+0 | 0 | 1/1 | yes | none | 2/2 | #281&nbsp;Closed |
| `lane-cigreen/dual-write-gates` | `28d42732` | 2026-08-13 | 1 | contained | −0/+1 | 1 | 0/1 | no | none | 2/2 | #282&nbsp;Closed |
| `lane-cigreen/sast-install-split` | `963315e3` | 2026-08-14 | 3 | contained | −2/+0 | 0 | 2/2 | yes | `5a3e3a04` | 1/2 | #283&nbsp;Closed |
| `test/deny-credential-denylist-coverage` | `90b7b39c` | 2026-08-01 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `c8e7085e` | 2/2 | #261&nbsp;Merged |
| `wave3/ci-trigger` | `97ea5eab` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `44238e84` | 0/1 | #276&nbsp;Merged |
| `wave3/command-center` | `589d5422` | 2026-08-09 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `53c37c6c` | 30/31 | #280&nbsp;Merged |
| `wave3/monitor` | `a8e8c2d0` | 2026-08-09 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `fbedcdf6` | 9/9 | #279&nbsp;Merged |
| `wave3/program-b` | `e3245cea` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `25015ba9` | 4/5 | #278&nbsp;Merged |
| `wave3/skill-gate` | `147a2813` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `f15cddbf` | 2/2 | #277&nbsp;Merged |
| `docs/cursor-cli-bridges` | `fbc70f22` | 2026-08-27 | 15 | **partial** | −0/+14 | 14 | 0/14 | no | 65/70 | 65/70 | #290&nbsp;Closed |
| `fix/deny-credential-gaps` | `d3def686` | 2026-08-26 | 2 | **partial** | −1/+1 | 1 | 1/2 | no | 1/9 | 0/9 | #260&nbsp;Merged |
| `import/agents-fullstate-2026-08-28` | `c3cde97b` | 2026-08-28 | 1 | **partial** | −0/+1 | 1 | 0/1 | no | none | 2655/2665 | — |
| `wip/harness-additions-2026-08-28` | `fb075a2b` | 2026-08-28 | 8 | **partial** | −1/+7 | 7 | 1/8 | no | none | 3374/3432 | — |
| `wip/harness-workspace-supervisor-20260826` | `b0b29812` | 2026-08-26 | 2 | **partial** | −0/+2 | 2 | 0/2 | no | 17/44 | 17/44 | — |

## 8. Ready-to-run delete script

The script is embedded here rather than committed as a file, because this change is the report and
nothing else. To use it, copy the block into a scratch file outside the repo and run it from a
checkout:

```bash
# extract this section's code block, e.g.
awk '/^#!\/usr\/bin\/env bash$/,/^\[ "\$fail" = 0 \]/' \
    reconcile-flags/branch-retirement-2026-09-02.md > /tmp/retire-2026-07.sh
chmod +x /tmp/retire-2026-07.sh
/tmp/retire-2026-07.sh                       # dry run, tier 1 (65 contained)
/tmp/retire-2026-07.sh --apply               # delete those 65
/tmp/retire-2026-07.sh --include-residue     # dry run, all 74
/tmp/retire-2026-07.sh --include-residue --apply
```

**Two tiers, because "safe to delete" and "should be deleted" are different questions.** Tier 1
is the 65 contained branches: no signal finds anything on them that `main` lacks. Tier 2 is the 9
from §6 and requires `--include-residue`, so the three lanes with genuinely absent content (§6a)
cannot be swept out by a flagless invocation.

**It fails closed per branch.** Before deleting any branch it re-reads `origin` and requires:

1. `refs/tags/archive/2026-07/<branch>` exists on `origin` — no tag, no delete;
2. the tag **peels to exactly the branch's current remote tip** — so a branch that has moved since
   2026-09-02 is skipped rather than deleted at an untagged tip;
3. no open PR has the branch as its head, since deleting a head branch closes its PR.

Re-tagging a moved branch is deliberately *not* automated: a tip that moved after the archive pass
is new work, and what to do with it is a judgment call, not a script's.

Verified behaviour, run against the live remote in dry-run mode during this pass:

| check | result |
|---|---|
| tier 1 eligible | 65 of 65 — tag peels to tip for every one |
| tier 1 + tier 2 eligible | 74 of 74 |
| a branch with no archive tag (`docs/cursor-cli-bridges`, injected as a probe) | `SKIP … would lose the commits` |
| a branch that does not exist (`no-such-branch-xyz`) | `SKIP … already gone from origin` |
| `--apply` with `gh` absent from `PATH` | `refusing to --apply without the open-PR check` |
| `bash -n` | clean |

After a real `--apply` it re-checks that every archive tag still exists on `origin` and exits
non-zero if any is missing. The delete push is deliberately **not** `--atomic`: one
protected-branch refusal should not roll back 64 good deletions.

There are no open PRs in the repository as of this measurement, so criterion 3 is currently
vacuous — it is there for whenever this is actually run.

```bash
#!/usr/bin/env bash
# Delete the retired 2026-07 branches from origin. OWNER ACTION — nothing here ran in the pass
# that produced this file; the 74 archive tags did.
#
#   ./delete-2026-07-branches.sh                     # dry run, tier 1 only (default)
#   ./delete-2026-07-branches.sh --apply             # delete the 65 contained branches
#   ./delete-2026-07-branches.sh --include-residue   # dry run, all 74
#   ./delete-2026-07-branches.sh --include-residue --apply
#
# Fails closed per branch. A branch is deleted only when ALL of these hold, checked against the
# REMOTE at run time (not against this file's assumptions):
#   1. refs/tags/archive/2026-07/<branch> exists on origin;
#   2. that tag peels to exactly the branch's current remote tip — so a branch that MOVED since
#      2026-09-02 is skipped, not silently deleted at an untagged tip;
#   3. no open PR has the branch as its head.
#
# Re-tagging a moved branch is deliberately not automated: a tip that moved after the archive pass
# is new work, and what to do with it is a judgment call.
set -euo pipefail

REMOTE=origin
PREFIX="refs/tags/archive/2026-07/"
APPLY=0
INCLUDE_RESIDUE=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --include-residue) INCLUDE_RESIDUE=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# ---- tier 1: contained. Every changed path and/or the whole cumulative diff is already on main.
TIER1=(
  agent/detector-fix-fp
  chore/accounts-store-followups
  chore/retire-brace-expansion-ignore
  chore/statusline-gotchas-and-goal-short-20260724
  ci/gate-cloud-hub-full
  ci/unignore-wave3
  ci/wire-harness-suites
  ci/wire-hooks-regression-harness
  ci/wire-mcp-hub-suites
  cursor/setup-dev-environment-1fd0
  data/harness-sota-corpus-2026-07-19
  docs/ci-coverage-gap-report
  docs/fb-graph-cooldown-relanded
  feat/aws-cloud-hub
  feat/browser-rail
  feat/claim-verify-gate
  feat/closed-batch-config-editor
  feat/fb-instagram-parity
  feat/linkedin-mcp-userscope-registration
  feat/mcp-http-host-shared-transport
  feat/mcp-surface-census
  feat/proxy-mcp-mitmproxy
  feat/repo-map-grounding-pack
  feat/search-expansion-rrf-multilingual
  feat/social-corpus-extraction-skill
  feat/stdin-server
  feat/tg1-detector-self-test-toolchain
  feat/tg2-mutation-gate-toolchain
  feat/variant4-increment1-dbx-monitor-20260721
  feat/w2-a04
  feat/w2-b21
  feat/w2-f02
  feat/w2-k04
  feat/w2-m02
  feat/w2-m20
  fin/F02
  fin/F03
  fin/F04
  fin/F06
  fin/F09
  fix/accounts-clear-gitcrypt-error
  fix/agent-self-harness-parity
  fix/complete-tg1-detector-self-test
  fix/dead-mcp-detector-honours-disabled
  fix/derive-167-settlement
  fix/git-hygiene-repo-truncation-floor
  fix/harness-corpus-control-guard
  fix/hooks-webfetch-sentinel-and-browser-compress
  fix/linkedin-mcp-sdk-cves
  fix/mcp-health-agentmail-fbmessenger
  fix/osv-ignore-brace-expansion
  fix/sentinel-status-field-not-payload
  fix/skill-frontmatter-and-grok-pulls
  fix/stubscan-wrapped-comment
  fix/triage-dispatch-manifest-presence
  fix/triage-dispatch-wiring
  fix/triage-golden-standalone
  fix/triage-memory-spool-replay
  fix/triage-per-edit-check-secrets
  fix/use-vs-mention-result-scanner
  fix/w2-a04-flaky-descendant
  lane/mcp-consolidation
  reconcile/harness-drift-wave2
  salvage/codex-scoping-layer
  w2-c16-error-taxonomy
)

# ---- tier 2: carries residue that never reached main. Requires --include-residue.
#      The archive tag preserves the commits either way; what deletion drops is the branch as a
#      place the residue is still visible. See §6 of the report before enabling this tier.
TIER2=(
  add-databricks-fanout-harness
  chore/enshrine-runtime-config
  chore/sync-from-live-20260725
  feat/monitorcore-codexsource
  fin/F05
  fin/F07
  fix/ssh-platform-cleanup-20260720
  fix/ui-audit-dead-button-noise-subtraction
  salvage/mcp-health-sync-20260725
)

BRANCHES=("${TIER1[@]}")
if [ "$INCLUDE_RESIDUE" = 1 ]; then BRANCHES+=("${TIER2[@]}"); fi

echo "remote:          $REMOTE"
echo "tier 1:          ${#TIER1[@]} contained"
echo "tier 2:          ${#TIER2[@]} with residue ($([ "$INCLUDE_RESIDUE" = 1 ] && echo INCLUDED || echo excluded))"
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

## 9. The 74 tag names

All annotated, all on `origin`, all peeling to the branch tip they name. The tag name is
`archive/2026-07/` + the branch name verbatim, so the mapping needs no lookup table; the list is
here so the report can be checked against the remote without a checkout.

```bash
git ls-remote --tags origin 'refs/tags/archive/2026-07/*' | grep -c '\^{}'   # -> 74
```

| # | archive tag | tip |
|---:|---|---|
| 1 | `archive/2026-07/add-databricks-fanout-harness` | `f1a009e6` |
| 2 | `archive/2026-07/agent/detector-fix-fp` | `def74263` |
| 3 | `archive/2026-07/chore/accounts-store-followups` | `20665bc2` |
| 4 | `archive/2026-07/chore/enshrine-runtime-config` | `4bcc65ec` |
| 5 | `archive/2026-07/chore/retire-brace-expansion-ignore` | `9d8139d5` |
| 6 | `archive/2026-07/chore/statusline-gotchas-and-goal-short-20260724` | `ace747b1` |
| 7 | `archive/2026-07/chore/sync-from-live-20260725` | `64340915` |
| 8 | `archive/2026-07/ci/gate-cloud-hub-full` | `eaa42fc2` |
| 9 | `archive/2026-07/ci/unignore-wave3` | `cefff8db` |
| 10 | `archive/2026-07/ci/wire-harness-suites` | `5d4ee9d9` |
| 11 | `archive/2026-07/ci/wire-hooks-regression-harness` | `defc7364` |
| 12 | `archive/2026-07/ci/wire-mcp-hub-suites` | `4135283a` |
| 13 | `archive/2026-07/cursor/setup-dev-environment-1fd0` | `69172393` |
| 14 | `archive/2026-07/data/harness-sota-corpus-2026-07-19` | `93e09f6b` |
| 15 | `archive/2026-07/docs/ci-coverage-gap-report` | `9b211603` |
| 16 | `archive/2026-07/docs/fb-graph-cooldown-relanded` | `7da5fddf` |
| 17 | `archive/2026-07/feat/aws-cloud-hub` | `303fdd64` |
| 18 | `archive/2026-07/feat/browser-rail` | `dfa16817` |
| 19 | `archive/2026-07/feat/claim-verify-gate` | `ab7aa065` |
| 20 | `archive/2026-07/feat/closed-batch-config-editor` | `e64ae329` |
| 21 | `archive/2026-07/feat/fb-instagram-parity` | `f81f17d5` |
| 22 | `archive/2026-07/feat/linkedin-mcp-userscope-registration` | `75a550aa` |
| 23 | `archive/2026-07/feat/mcp-http-host-shared-transport` | `1b07822e` |
| 24 | `archive/2026-07/feat/mcp-surface-census` | `6a584461` |
| 25 | `archive/2026-07/feat/monitorcore-codexsource` | `b3127f15` |
| 26 | `archive/2026-07/feat/proxy-mcp-mitmproxy` | `4bfc1581` |
| 27 | `archive/2026-07/feat/repo-map-grounding-pack` | `1b250e66` |
| 28 | `archive/2026-07/feat/search-expansion-rrf-multilingual` | `f4a7c34f` |
| 29 | `archive/2026-07/feat/social-corpus-extraction-skill` | `43bc9133` |
| 30 | `archive/2026-07/feat/stdin-server` | `4325e52e` |
| 31 | `archive/2026-07/feat/tg1-detector-self-test-toolchain` | `9f79cc0a` |
| 32 | `archive/2026-07/feat/tg2-mutation-gate-toolchain` | `d34d91af` |
| 33 | `archive/2026-07/feat/variant4-increment1-dbx-monitor-20260721` | `3da8adef` |
| 34 | `archive/2026-07/feat/w2-a04` | `388389a1` |
| 35 | `archive/2026-07/feat/w2-b21` | `5c7d8496` |
| 36 | `archive/2026-07/feat/w2-f02` | `b9f1339d` |
| 37 | `archive/2026-07/feat/w2-k04` | `999732c5` |
| 38 | `archive/2026-07/feat/w2-m02` | `521cbac6` |
| 39 | `archive/2026-07/feat/w2-m20` | `45a53b37` |
| 40 | `archive/2026-07/fin/F02` | `f0969cbc` |
| 41 | `archive/2026-07/fin/F03` | `cfeae5ec` |
| 42 | `archive/2026-07/fin/F04` | `ca60e89d` |
| 43 | `archive/2026-07/fin/F05` | `8b709251` |
| 44 | `archive/2026-07/fin/F06` | `5bce916a` |
| 45 | `archive/2026-07/fin/F07` | `bbd90540` |
| 46 | `archive/2026-07/fin/F09` | `803b5781` |
| 47 | `archive/2026-07/fix/accounts-clear-gitcrypt-error` | `212532bf` |
| 48 | `archive/2026-07/fix/agent-self-harness-parity` | `1b89e439` |
| 49 | `archive/2026-07/fix/complete-tg1-detector-self-test` | `30252128` |
| 50 | `archive/2026-07/fix/dead-mcp-detector-honours-disabled` | `6cc5feb9` |
| 51 | `archive/2026-07/fix/derive-167-settlement` | `847c21f7` |
| 52 | `archive/2026-07/fix/git-hygiene-repo-truncation-floor` | `f0cbb4d8` |
| 53 | `archive/2026-07/fix/harness-corpus-control-guard` | `2212f4ca` |
| 54 | `archive/2026-07/fix/hooks-webfetch-sentinel-and-browser-compress` | `5cdc4b00` |
| 55 | `archive/2026-07/fix/linkedin-mcp-sdk-cves` | `782c8573` |
| 56 | `archive/2026-07/fix/mcp-health-agentmail-fbmessenger` | `26be01d0` |
| 57 | `archive/2026-07/fix/osv-ignore-brace-expansion` | `f87cf6a5` |
| 58 | `archive/2026-07/fix/sentinel-status-field-not-payload` | `396a4578` |
| 59 | `archive/2026-07/fix/skill-frontmatter-and-grok-pulls` | `1baa7ad5` |
| 60 | `archive/2026-07/fix/ssh-platform-cleanup-20260720` | `bf4eb2a7` |
| 61 | `archive/2026-07/fix/stubscan-wrapped-comment` | `f4935703` |
| 62 | `archive/2026-07/fix/triage-dispatch-manifest-presence` | `228e3849` |
| 63 | `archive/2026-07/fix/triage-dispatch-wiring` | `6c2a6b32` |
| 64 | `archive/2026-07/fix/triage-golden-standalone` | `c64a46ca` |
| 65 | `archive/2026-07/fix/triage-memory-spool-replay` | `340588d0` |
| 66 | `archive/2026-07/fix/triage-per-edit-check-secrets` | `c91e40f2` |
| 67 | `archive/2026-07/fix/ui-audit-dead-button-noise-subtraction` | `1591a858` |
| 68 | `archive/2026-07/fix/use-vs-mention-result-scanner` | `1fc1e4e7` |
| 69 | `archive/2026-07/fix/w2-a04-flaky-descendant` | `9accffa1` |
| 70 | `archive/2026-07/lane/mcp-consolidation` | `a7aedb75` |
| 71 | `archive/2026-07/reconcile/harness-drift-wave2` | `6618d4f9` |
| 72 | `archive/2026-07/salvage/codex-scoping-layer` | `77a53ef5` |
| 73 | `archive/2026-07/salvage/mcp-health-sync-20260725` | `64340915` |
| 74 | `archive/2026-07/w2-c16-error-taxonomy` | `318565b1` |

## 10. What is still open for the owner

1. **Whether to delete at all.** §8 tier 1 (65) is the low-risk half. Nothing in this pass argues
   the branches *must* go — only that going is now non-destructive.
2. **`feat/monitorcore-codexsource`'s live-tailing path** (§6a.1) — 4 files / 120 lines of a wanted feature
   that `main` does not have, on a branch whose PR was closed. Salvage or drop, then retire.
3. **`chore/enshrine-runtime-config`'s `test_stoploop_boundary.py`** (§6a.2) — 189 lines against a
   tree that has since moved. Belongs to the harness-lineage decision in
   `harness-lineage-2026-09-01.md`, not here.
4. **Tag the August block.** The 17 unmerged non-July branches (§7) hold **9,781 absent lines**
   against the July set's 6,344, and 6,435 of those are one unshipped subsystem on
   `wip/harness-workspace-supervisor-20260826`. They are unprotected right now.
5. **`RECONCILE-STATE_2026-09-01.md` §6b item 5** can be updated to reflect that the confirmation
   step is done and the tags exist; items 1–4 and 6 of that list are untouched by this pass.
6. **Item 6 of that list — rotating the pasted personal access token — is still not done**, and
   this pass did not touch it. Recorded here so it does not fall off the list.

## 11. Rules this pass held to

- No branch deleted, no branch moved, no branch created except the one carrying this report.
- No merge, no force push, no amend, no rebase of anything on the remote.
- No secret read, written or rotated; no credential material touched.
- Every tag created is additive; the 20 pre-existing `rescue/*` tags were left exactly as they were.
- Every figure in this document came out of a command in §2 run in this checkout, and the two
  places where a first measurement was wrong (§2a) say so rather than quietly showing the second.