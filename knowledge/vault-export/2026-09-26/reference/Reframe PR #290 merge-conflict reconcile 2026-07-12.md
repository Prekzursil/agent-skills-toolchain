---
title: 'Reframe PR #290 merge-conflict reconcile 2026-07-12'
type: reference
permalink: main/reference/reframe-pr-290-merge-conflict-reconcile-2026-07-12
tags:
- reframe
- git
- merge-conflict
- worktree
- pr-290
- gotcha
---

# Reframe PR #290 merge-conflict reconcile 2026-07-12

Resolved the CONFLICTING/DIRTY state on Reframe PR #290 (`feat/v1.5-director-screen`) after #291 (shell-polish, red-text AA) + #292 (Export/Deliver) merged to main first. Result: PR now `mergeable: MERGEABLE`. Merge commit `b127e1c` pushed (fast-forward, no force).

## ⭐ Reusable gotcha (cost real investigation steps)
In the agent-worktree setup, the worktree's **local** branch can be STALE vs the true remote PR head. Here `git checkout feat/v1.5-director-screen` landed on a local branch at `ee1f092`, but the actual `origin/feat/v1.5-director-screen` PR head was `0fedb1a` (one commit ahead — the `fix(director): AA-safe red text token` commit that adds `--status-error-text` + conformance guards, i.e. the very thing the conflict is about). Merging into the stale head would have produced a WRONG, non-representative result.
- **Rule:** before merging in a worktree, ALWAYS `git ls-remote origin <branch>` and compare to local HEAD. If they differ, `git fetch origin <branch>:refs/remotes/origin/<branch>` then `git reset --hard origin/<branch>`.
- An explicit-refspec fetch (`git fetch origin <branch>`) only writes FETCH_HEAD; it does NOT store `refs/remotes/origin/<branch>` — use the `<src>:<dst>` refspec form to store the remote-tracking ref.

## Conflict resolution (what was kept/removed)
- **tokens.css**: add/add conflict was ONLY on the explanatory comment; git had already unified the identical `--status-error-text: #ff6b6b;` def line. Kept main's canonical comment, removed #290's duplicate comment block.
- **tokens.conformance.test.ts**: auto-merged (no conflict). Both red-text guards coexist and are DISTINCT — #290's `describe('...soft-error wash (PR #290)')` composite-over-`--status-error-soft` check (via `toRgba()`/`over()` helpers) AND main's `describe('...DoD contrast floor (v1.5 shell-polish)')` direct-on-plane + Library-routing check. Verified every helper (`toRgb`/`toRgba`/`over`/`relLum`/`contrast`) defined exactly once — no dup from auto-merge. 32 conformance tests pass.
- **views/director.css**: kept #290's `.director-view__error { color: var(--status-error-text) }` — the real Director contrast fix.
- **App.tsx**: auto-merged; Director route (#290) + Export/Deliver views (#291/#292) both preserved.

## Gate results (actual)
- `npm ci`: exit 0 (lockfile unchanged by the merge; app node_modules built fresh in worktree)
- `tsc --noEmit`: exit 0
- `vitest run --coverage`: **203 files / 3448 tests all pass**, coverage **100% lines/branches/functions/statements** (v8 provider, thresholds in `app/vitest.config.ts`). Ran WITHOUT the memory-cap fallback — did NOT OOM despite ~6.3 GB free (the `NODE_OPTIONS=--max-old-space-size=3072 --no-file-parallelism` fallback was not needed).
- `pre-commit run --files`: oxlint / biome-format / gitleaks all Passed; ruff skipped (no py). No auto-fixes.

## Aftermath
GitHub `mergeStateStatus: BLOCKED` post-push = branch-protection waiting on CI checks for the new commit (NOT a conflict); `mergeable: MERGEABLE` confirms the conflict is gone. `headRefOid` = `b127e1c`.
