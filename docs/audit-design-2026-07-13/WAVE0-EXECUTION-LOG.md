---
title: WAVE0-EXECUTION-LOG
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/wave0-execution-log
---

# Wave-0 Execution Log + Learnings (2026-07-13)

The reliability-bootstrap wave of the unified harness control-plane program, run
**metaswarm-orchestrated** (owner-chosen) — each work-unit through the 4-phase loop
(IMPLEMENT → VALIDATE → ADVERSARIAL-REVIEW → COMMIT), every code WU independently
reviewed, then a final holistic review (SHIP_WITH_NITS, deploy-ready, 498 tests green).

## Commits (branch `chore/enshrine-runtime-config`, on `dd5366b`)

| # | Commit | WU | Reviewed |
|---|--------|----|----------|
| 1 | `48eab3a` | task-9 codex-invoke primitive + profiles + `$CODEX_HOME/profiles` edit-guard (held work, landed first to unblock) | tests (64) |
| 2 | `7d27575` | **WU-1** A1: Stop re-entrancy guard hoisted to the dispatcher boundary + terminal-id redaction | adversarial + empirical RED-without-fix |
| 3 | `b629532` | WU-1 nits: DRY the re-entrancy predicate (`adapters.is_reentrant_trigger`) + OR-in raw `stop_hook_active` (Codex-robustness) | re-validated |
| 4 | `3de2a77` | **WU-3** back-port 22 daily-gem skills (pure-additive; manifest 85→107) | additive-safety validated |
| 5 | `dd06122` | **WU-4** SHADOW enforcement scaffold — 3 gates (cleanup / doc-reconcile / harness-change→doc) | adversarial + 25/25 invariant probe |
| 6 | `a68a340` | WU-4 nits: honest gate-3 advisory text + cooldown-before-glob | re-validated |
| 7 | `9633381` | **WU-2** thread `source_commit` through `deploy()`'s receipt (provenance) | tests + final review |
| 8 | `f811383` | docs: RFC + evidence + grill + recon (3 census blobs gitignored) | — |

WU-5 (plugin-Stop triage) concluded *keep all 3, no stale state* (recon + review), no code.

## Deferred (owner decisions / non-blocking)
- **Live deploy** → deferred; fold with the `hooks.claude`/`hooks.codex` registration reconcile
  (task #1) into one clean code+config sync, owner-present. Live already loop-safe.
- **3 review nits** (non-blocking): register `StopFailure` in `registration.EVENTS` (or a
  direct-dispatch-only comment); scaffold fail-open branches under-covered; no coverage
  threshold governs the Python harness tree (85%).
- Wave-2 = hardened CAS-lite-EXTEND deployer (D1=B). Wave-3 = monitoring / orchestration / mingling.

## Reusable learnings

1. **Boundary-hoist for re-entrancy.** A re-entrancy short-circuit belongs at the *dispatcher
   boundary* (before module fan-out), not inside one module — that makes it structural, covers
   every current/future Stop-producing module AND the separate plugin Stop hooks, and can't be
   defeated by adding a new module. The module-local guard is kept only as defense-in-depth.

2. **SHADOW-gate discipline (never reintroduce the loop).** A new enforcement gate MUST be:
   never-on-Stop (whitelist SessionStart/PreToolUse — a Stop-time injection is what caused the
   incident), fail-open (guarded detectors + the dispatcher's own per-module try/except),
   zero-teeth in SHADOW (max verdict `inject`, never `block`; `block`/`deny` not even valid
   modes), kill-switched (global `HARNESS_ENFORCE` + per-gate env), and shadow-sink-only
   (never `terminal.jsonl`/ledger). Verify each invariant with a dedicated test.

3. **Scoped-commit discipline on a shared worktree.** Explicit `git add <paths>` + a
   `git diff --cached` check before *every* commit; never `git add -A`. Land held/orthogonal
   work as its own coherent commit FIRST to clear the entangled file. Result here: 8 clean
   commits, zero cross-WU contamination, held task-9 preserved rather than swept or lost.

4. **Empirical RED-without-fix beats reading.** The strongest fix verification is a reviewer
   *neutering* the guard in an isolated scratch copy and running the tests to prove the tests
   fail without it — distinguishing a genuine proof from a test that passes for the wrong reason
   (both WU-1 and WU-4 reviews did this, and WU-1's review caught that a subprocess test was only
   a regression guard, not a boundary proof).

5. **Verify the brief, don't obey it.** The WU-3 coder caught a stale instruction ("no angle
   brackets in skill descriptions") that was Anthropic's `quick_validate.py` rule, NOT this
   repo's — the real validator is `hooks/semantic-router/build_index.py`, which accepts them.
   Stripping them would have diverged the repo from its canonical source. (Stale memory corrected.)

6. **Deploy-then-check IS the drift detector — and drift happens in the wild.** `install.py
   --check` before deploying found `hooks.claude` had drifted since the enshrine (contradicting
   the earlier "hooks.claude OK" record) — i.e. the live config is being modified outside the
   repo. A discovered drift on the deploy target is a *surface-it-don't-proceed* trigger, not a
   step to overwrite blindly. This is the exact failure mode the SSOT engine exists to close.