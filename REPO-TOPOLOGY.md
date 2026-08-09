# Repository topology — the single source of truth

**Measured 2026-08-09.** Read this before deciding where to edit. Every number below came from
`git rev-parse --git-common-dir` and `git rev-list --all`, not from directory names.

## The one-line answer

There is **ONE** repository — `https://github.com/Prekzursil/agent-skills-toolchain.git` — reached
through **9 local checkouts** spread across **2 independent object stores**. The directory named
`ast-integrate` is not a separate project; it is a *worktree*, and it is the one holding `main`.

**The remote is the SSOT. Locally, edit in `~/source/ast-integrate`.**

## Why this is confusing — and why it is NOT a mistake anyone made

The *main checkout* of the repository — `~/source/agent-skills-toolchain` — is **not on `main`**,
and **it never can be.** Git allows a branch to be checked out in exactly one place, and
`ast-integrate` holds `main`. Attempting it fails outright:

```
$ git -C ~/source/agent-skills-toolchain checkout main
fatal: 'main' is already used by worktree at 'C:/Users/Prekzursil/source/ast-integrate'
```

So the path whose name implies "the repo" cannot be the path that has `main`. This document
originally called that an inversion to be fixed; **that was wrong** — it is inherent to the worktree
topology, not a mistake to correct. The only fix available is naming/documentation, or moving `main`
into this checkout and giving `ast-integrate` something else (disruptive, and not worth it).

**Resolved 2026-08-10:** the checkout was parked for 16 days on
`fix/mcp-health-agentmail-fbmessenger` (165 behind `main`, 24 dirty, 1 unpushed). It is now a
**detached HEAD at `origin/main`** — current content, 0 unpushed, 2 dirty (both `accounts.json`,
the live rotation pool, deliberately untouched). The stale branch survives locally and on the
remote; its one unpushed commit was pushed to `salvage/mcp-health-sync-20260725` because the branch
was **1 ahead and 16 behind its own upstream**, so a plain push would have been rejected.
Working files were preserved, never deleted: `stash@{0}` (8 modified tracked files), and 33 files
under `~/.claude/ast-salvage-20260810/`.

## Store A — canonical. `~/source/agent-skills-toolchain/.git`

912 commits · 275 refs · 6 checkouts.

| role | path | branch | note |
|---|---|---|---|
| MAIN checkout | `~/source/agent-skills-toolchain` | *detached* @ `origin/main` | 2 dirty (both `accounts.json`). Cannot hold `main` — see above. |
| worktree | `~/source/ast-integrate` | `main` | **← canonical working copy. Edit here.** |
| worktree | `~/source/ast-harness-reconcile` | `chore/enshrine-runtime-config` | clean |
| worktree | `~/source/ast-statusline-capture` | `chore/statusline-gotchas-and-goal-short-20260724` | clean |
| worktree | `D:\ckwt\cookie-bridge-skill` | `feat/cookie-bridge-skill-20260724` | clean, off-drive |
| worktree | `D:\inc1-wt\ast-increment1` | `feat/variant4-increment1-dbx-monitor-20260721` | 1 dirty, off-drive |

Worktrees share one object store **and one index-adjacent surface**: a broad `git add -A` in any of
them can sweep a sibling's work. Stage explicit paths and check `git diff --cached` before committing.

## Store B — redundant. `~/source/ast-patch167/.git`

724 commits · 128 refs · 3 checkouts. A **separate full clone** of the same GitHub repo, so it
drifts independently and silently.

| role | path | branch |
|---|---|---|
| MAIN checkout | `~/source/ast-patch167` | `fix/deny-credential-gaps` (1 dirty) |
| worktree | `~/source/_verify_M04_tree` | detached at `d9ec177` |
| worktree | `~/source/_verify_M13` | detached at `be60f18` |

Its `origin/main` is pinned at `07f465f` (2026-08-03) while real main is `53c37c6c` — **39+ commits
stale**. Anything measured against store B's `origin/main` is measuring the wrong baseline. That is a
live footgun, not a theoretical one.

### Is anything trapped in store B? No — verified, not assumed

Store B holds 25 commits absent from store A. 9 are Dependabot commits that exist on remote branches.
The other **16 have no remote branch at all** and live on local branches `pr242 / pr244 / pr245 / pr249`.

That looked like data at risk. It is not, and the check was content-level rather than ancestry-level
because squash-merge makes a fully-merged branch report as ahead:

| branch | files touched | byte-identical on main | differs | absent from main |
|---|---|---|---|---|
| `pr242` | 120 | 118 | 2 | **0** |
| `pr244` | 122 | 121 | 1 | **0** |
| `pr245` | 122 | 121 | 1 | **0** |
| `pr249` | 123 | 122 | 1 | **0** |

All four PRs merged 2026-07-30. Zero files are absent from main.

The residual differences are two CI files, and direction matters — a one-directional read is how a
prior sweep produced 31 errors all pointing at data loss, so both directions were measured:

- `skill-dual-write.yml` — 0 branch-only lines, 7 main-only. **Main is a superset.**
- `quality.yml` — 13 branch-only lines, 490 main-only: genuinely **DIVERGED**. The 13 are a
  `gate-tests-coverage agentify-desktop` job plus its `--lockfile` entry. `tools/web/agentify-desktop`
  has **0 files on main** (control: 2,200 files under `tools/`), and main's own `quality.yml:1412`
  documents "the slot the agentify-desktop retirement vacated". Those lines reference a tree that was
  deliberately deleted. Restoring them would point a CI job at a nonexistent directory.

**Conclusion: store B is fully redundant.** Retiring it loses nothing. UNVERIFIED: the 1 uncommitted
file in `ast-patch167` and the 24 in `agent-skills-toolchain` were not part of this comparison —
they are uncommitted, so no commit-level check can see them. Settling experiment: diff each working
file against `origin/main:<path>` before removing either tree.

## Rules that follow from this

1. **Edit in `~/source/ast-integrate`.** It holds `main`. Nothing else does.
2. **Never treat a directory name as a repo identity.** Run
   `git rev-parse --git-common-dir` — two paths sharing that value are one repository, and identical
   blob counts prove nothing on their own (that is what first suggested this investigation, and it
   was true only because worktrees share an object store).
3. **Never measure a baseline in store B.** Its `origin/main` is 39+ commits stale. Fetch first, or
   use store A.
4. **Never use commit ancestry as delete authorisation.** Squash-merge makes merged branches report
   as ahead. Compare content with `git cat-file -p <rev>:<path>` — never `git archive`, which applies
   export-time EOL conversion and returns CRLF on this box, so identical files look different.
5. **`git worktree add` resolves the repo from cwd.** From a non-repo cwd it silently lands in an
   unrelated project; this happened on 2026-08-08 and pointed five agents at another session's
   repository. Always `git -C <intended repo> worktree add …` and verify with
   `git -C <path> remote get-url origin` before the first write.

## Recommended consolidation — NOT yet executed

- **Retire store B entirely** (`ast-patch167`, `_verify_M04_tree`, `_verify_M13`): 3 checkouts and a
  full object store, verified to hold no unique committed content. Triage the 1 uncommitted file first.
- ~~Put the main checkout back on `main`~~ — **impossible, and now closed.** Git forbids it (see
  above). Done instead on 2026-08-10: detached at `origin/main`, 24 dirty → 2, 1 unpushed → 0.
  Optional follow-up: rename `ast-integrate` to something that says what it is, since the naming
  is the only remaining half of the problem.

Store B retirement is still open, and touches a tree a running program is using.

## Detector notes — three probes that were wrong here, keep them in mind

1. **Identical blob counts prove nothing.** Worktrees share one object store, so the 13,921/13,921
   match that started this investigation was tautological. Use `git rev-parse --git-common-dir`.
2. **"Unpushed" depends on the baseline.** `origin/main..HEAD` gave 8; the branch's own upstream
   `origin/<branch>..HEAD` gave 1. The hygiene guard reported 1 and was right; a wrong baseline was
   used to accuse a correct instrument.
3. **`git status --porcelain` collapses untracked directories.** Checking `??` entries against tree
   paths found 4 checkout collisions; `--untracked-files=all` found **26**. Always expand with
   `-uall` before concluding a checkout is unblocked.
