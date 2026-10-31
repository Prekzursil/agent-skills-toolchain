---
paths:
- '**/.claude/**'
- '**/.agents/**'
permalink: dqverify-repo-20261013/rules/common/stale-megapr-reconcile
---

# Stale mega-PR reconcile — measure the conflict surface before you rebase

Cross-tool rule (Claude Code · Codex CLI · Antigravity). Applies to any git PR/branch
reconciliation. Ledger-proven on momentstudio #625 (2026-07-18).

## 1. MEASURE the real conflict surface before assuming a rebase marathon

A PR's *line count* is a terrible proxy for its *reconcile cost*. A **+72k-line / 288-commit**
stale PR (#625) turned out to have a **5-file** conflict surface — the bulk was new files, which
never conflict. Do NOT eyeball the diff size and reach for a multi-day rebase.

- **Do this first:** on a throwaway branch, `git merge --no-commit --no-ff <base>` then
  `git diff --name-only --diff-filter=U | wc -l`. That count — not the +/- lines — is the real
  work. `git merge --abort` after measuring.
- **Composition tells you more:** `git diff --name-status <merge-base> <pr-head> | awk '{print $1}' | sort | uniq -c`
  (A=added=no-conflict, M=modified=possible-conflict, D=deleted).

## 2. Resolution recipe (once the surface is known)

- **Deps:** if the stale branch has NO unique deps (`comm -23` its dep list against base's),
  take **base's** `package.json` + lockfile wholesale — base is the superset (Dependabot bumps).
- **Machinery/config files:** keep base's version unless the PR's intent is specifically to
  change them (respect any additive-only governance charter — don't delete deferred machinery).
- **Tests:** graft only **self-contained** tests (a test that brings its own setup). A test that
  depends on the *other* side's helpers (`mount()`, a `Stubs` type, `NavInternals`) will NOT
  compile if grafted — leave those for the branch's owning session, and say so in the PR.
- **Runtime-dependent assertions:** a stale `expect(navItems.length).toBe(10)` that merged-base's
  new code makes 11 — do NOT guess the number. Flag it as a follow-up for the owner + let CI
  pin it. Guessing a runtime value is fabrication.

## 3. Superset check

If PR-B's branch already merged PR-A's work (`git log B..A` empty), **B ⊇ A** — reconcile from B
and close A in its favour; don't reconcile both.

*Companion: the `reconcile-all-branches-prs` skill (analysis) and basic-memory
`momentstudio-reconcile-learnings-*`.*