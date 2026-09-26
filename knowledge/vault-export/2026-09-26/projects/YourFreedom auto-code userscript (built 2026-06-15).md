---
title: YourFreedom auto-code userscript (built 2026-06-15)
type: note
permalink: main/projects/your-freedom-auto-code-userscript-built-2026-06-15
tags:
- userscript
- yourfreedom
- tampermonkey
- automation
- subagent-driven
---

# YourFreedom Auto Code Submitter — userscript

**GitHub (PRIVATE):** https://github.com/Prekzursil/yourfreedom-autocode (default branch `master`). **Release v1.0.0** (2026-06-16): https://github.com/Prekzursil/yourfreedom-autocode/releases/tag/v1.0.0 — asset `yourfreedom-autocode.user.js` attached for one-click install.
**Local repo:** `C:\Users\Prekzursil\projects\yourfreedom-autocode` (master = full project; `feat/userscript-implementation` local-only, merged).
**Deliverable:** `dist/yourfreedom-autocode.user.js` (Tampermonkey/Violentmonkey). Built via brainstorming → spec → writing-plans → 5-round adversarial plan-gate (PASS) → subagent-driven TDD execution. Docs: README (full guide), CHANGELOG.md, LICENSE, docs/specs + docs/plans.

## What it does
Batch-enters weekly yourfreedom.ro / mypass promo codes. Verify-before-advance (never skip), classify VALID/VALID_RETRY/ALREADY/INCORRECT, cooldown→≥15s growing backoff (never tight retry), circuit breaker, persist/resume across reloads (two-phase SUBMITTED→RESOLVED, reconcile not re-submit), leader election (one tab), 3 pacing profiles (safe/balanced/adaptive-AIMD). Cross-browser (Chrome/Edge/Firefox via Tampermonkey or Violentmonkey — NOT Greasemonkey). Android = same script on Firefox-Android+TM/VM or Kiwi. 14 src modules, esbuild→one .user.js.

## Status (2026-06-16)
- CODE-COMPLETE + unit-verified: 118 tests/20 files, pure modules 100% coverage, DOM glue 90/85 (user-approved split), node --check clean, builds, grant-survival gate.
- LIVE-tested (injection) PARTIAL PASS: confirmed load, parse, run-state, two-phase SUBMITTED persist, governor charge, submit on the real form; nothing consumed.
- **⭐ KEY LIVE FINDING: the site does a FULL PAGE RELOAD on every submit.** Kills an injected script (injection can't complete a multi-code run) but the real @match Tampermonkey script re-runs each load and auto-resumes from the persisted marker → VALIDATES the two-phase+resume architecture as REQUIRED. Each code = 2 paced endpoint hits (original + reconcile); valid code counts once (VALID_RETRY on reconcile). Repeated reloads during a batch are normal.
- STILL PENDING: one real Tampermonkey-installed end-to-end run (only way to exercise resume-across-reload). Independent final code-review optional (/code-review ultra; subagents were account-limit-blocked).

## Site facts (live)
Valid → counter "N minute de libertate acumulate" +5/+10 + modal "Ai câștigat N minute" (auto-closes ~2-3s). Incorrect → "Codul introdus este incorect". Already → "Acest cod a fost deja înscris în Campanie". Cooldown only on sub-~2s resubmits. Counter NOT reliable cross-session (saw 50→15 after re-login); "already entered" = reliable proof of registration. **Submit reloads the page.** Session drop → mypass date-of-birth re-login (I must NOT enter DOB — user does). 25 codes/week. jQuery, main-page DOM, fill via native value setter + input/change.

## Durable lessons (build-time)
- **Adversarial plan-gate reviews TEXT, not runtime** — converged 5→1→2→2→0 blockers, but MISSED two contradictions only RUNNING tests caught: parser test↔impl (prose "IGNORE" matched code regex → require a digit) and governor.js **duplicate ESM import** (vitest's esbuild silently dedupes → `node --check`/real bundle throw). → **Run `node --check` per module**; consolidate imports in multi-part modules.
- **100% BRANCH coverage** needs explicit tests for defensive `|| / ?? / null-guard` fallbacks.
- **Parallel subagents share the git index** → scoped `git add <files>` (never `-A`); build sequentially.
- **Subagent account-session-limit** can kill an implementer mid-task; fall back to building from the plan's verbatim code in the main session.
- **Injected-userscript testing can't survive reload-on-submit sites** — validate by installing, not injecting.
