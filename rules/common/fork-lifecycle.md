---
paths:
- '**/*'
permalink: dqverify-repo-20261013/rules/common/fork-lifecycle
---

# Fork Lifecycle (owner directive 2026-09-30 — standing rule, never closes)

> Directive source: owner instruction 2026-09-30 — "for fork repos, we can modify and
> integrate them or repurpose, and not delete the fork… occasionally update from the
> original… reconcile whether it's our version or a modified one… best of all worlds
> policy without regressions… prevent accidents, loss of data, regressions or missed
> opportunities." This rule fills in the discipline around that directive.

Forked/cloned third-party repos on this estate are **never deleted**. They are living
working copies with an upstream relationship. Lifecycle:

## 1. WORK — modify, integrate, repurpose freely
- Local commits on the clone are normal and encouraged; the clone is the upstream-tracking
  working copy for our modifications.
- NEVER push to the third-party remote (push stays disabled, e.g. `no_push` URL, or points
  at our private mirror). NEVER force-push any remote of a fork.

## 2. INTEGRATE — when fork work becomes load-bearing, port it into agent-skills-toolchain
- Target layout: `tools/mcp/<name>/` (or the fitting toolchain home), with original
  LICENSE preserved and upstream attribution in the README ("modified from <upstream-url>,
  local deltas: …").
- The clone SURVIVES integration — it stays as the upstream-facing working copy.
  Integration is additive, not a migration-and-delete.

## 3. MIRROR — unique local work must never be one disk away from loss
- A fork holding unique commits or untracked scripts (e.g. insta-mcp's 2FA/challenge
  tooling) gets a **private mirror** (`github.com/Prekzursil/<name>-fork`) or its unique
  work is committed to the toolchain. Stashes and untracked files are not version control.
- **Before ANY upstream sync/rebase on a fork: enumerate `git status --porcelain -uall`
  and commit or mirror every unique item.** (Accident-prevention gate.)

## 4. SYNC — upstream updates are reconciled, never merged blindly
- Periodically `git fetch upstream` and review `git log HEAD..upstream/main --oneline`.
- Every incoming change gets one of four verdicts, recorded in the fork's
  `FORK-NOTES.md` (create on first sync):
  1. **ours-better** — skip the commit, record why (silently taking it is a regression).
  2. **upstream-better** — take it, adapt our deltas on top.
  3. **defect-we-also-have** — take it first, it wins over our version.
  4. **idea-worth-stealing** — port the concept/design into our version, not the commit.
- Default conflict resolution favors OUR modified version, except verdict-3 defects.
- **Regression gate after every sync:** the fork's smoke path (probe/keepalive/service
  start against fixtures) runs before the sync is called done. A sync that breaks local
  modifications is reverted, not "fixed forward" under pressure.

## 4b. LOCALITY (owner amendment 2026-09-30: "don't keep the forks locally as well, just github, if we don't use them and we have our own version")
- A local clone exists ONLY while at least one holds: (a) an active program dependency
  (runtime, scripts, node_modules/venv in live use, or gitignored data the program reads),
  (b) unpushed unique work, or (c) an in-flight upstream sync.
- When integration is complete + the mirror is pushed + nothing live depends on the local
  path → **the local clone is RETIRED (deleted); the GitHub mirror is the SSOT**; re-clone
  on demand when the fork is next needed.
- NEVER retire a local clone while it holds the only copy of anything: sessions,
  gitignored secrets, and data dirs move to the vault (or their own runtime home) FIRST,
  verified by hash, before deletion. Retiring ≠ data loss.
- Current applications (2026-09-30): insta-mcp stays local (IG program actively runs
  probe/keepalive from it + frozen node_modules + live session data); whatsapp-mcp is a
  retire-candidate after unique-work export (its auth_info.bak-* session material moves
  to the vault, never the mirror).

## 5. RECONCILE (periodic health check — missed-opportunity prevention)
- At least quarterly (or when upstream releases): a short diff review of
  `upstream/main..HEAD` asking three questions: (a) have we drifted so far that
  re-integration is now cheaper as a re-fork? (b) does upstream now cover features we
  hand-built (verdict-2 candidates we can retire)? (c) are there new upstream ideas we
  have not covered (verdict-4 candidates)? Findings go to FORK-NOTES.md or a loop.

## Hard NEVERs
- Never delete a fork clone to "tidy up" or after integration.
- Never merge/rebase upstream with dirty or untracked unique work in the tree.
- Never let an upstream sync auto-overwrite local modifications (no `theirs`-strategy
  blanket merges).
- Never push local modifications or secrets to the third-party upstream remote.

Applies to: `insta-mcp`, `whatsapp-mcp` (third-party clones with local work), and any
future fork. Original (non-fork) repos we own remain governed by the consolidation
directive (consolidate into toolchain, then the original remote may be retired —
retirement still requires the content-verified-in-toolchain check).