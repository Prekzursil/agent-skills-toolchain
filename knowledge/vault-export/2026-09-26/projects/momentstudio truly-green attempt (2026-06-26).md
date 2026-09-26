---
title: momentstudio truly-green attempt (2026-06-26)
type: note
permalink: main/projects/momentstudio-truly-green-attempt-2026-06-26
tags:
- momentstudio
- qzp
- ci
- green
- reframe
---

# momentstudio truly-green attempt (2026-06-26)

Goal: drive Prekzursil/momentstudio TRULY green like Reframe (lean `quality` gate green on main + 0 PRs + 0 issues + 0 dependabot/code-scanning alerts) by retiring QZP machinery.

## DONE (in scope, achieved)
- DISABLED 24 QZP/SaaS workflows (agent-*, audit-*, applitools/chromatic/browserstack, codacy/codecov, quality-zero-{backlog,gate,platform,remediation}, scanner-gate, snyk, sentry-release, kpi/curation digests, branch-protection-audit, copilot-setup-steps). KEPT 9 active: backend, frontend, compose-smoke, codeql, dependency-review, deploy-production-manual, pr-labeler, quality, release.
- Branch protection on main: set required check = ONLY `quality` (was 17 stale SaaS contexts). Ruleset 14488873 DISABLED (matching Reframe whose ruleset is also disabled; Reframe requires only `quality`).
- CLOSED all 56 open issues (ALL authored by app/github-actions = QZP digests/audits; zero human issues). Comment: "Superseded: QZP retired; migrated to the lean quality gate."
- CLOSED 11 PRs: #603-608 (bumps to retired quality-zero-platform reusable workflows), #578 (auto ECC bundle), #488/#460 (QZP rollout/strict-zero), #487 (lockfile for retired Coverage100 gate, conflicting), #576 (QZP drive-to-zero CodeQL fix, conflicting).
- Opened cleanup PR #616 (chore/retire-qzp-machinery): deletes 23 retired workflow .yml + .codacy.yaml/codecov.yml/sonar-project.properties/.qlty. Kept .quality/opengrep (used by lean gate).

## HARD BLOCKERS to TRULY_GREEN (genuine, NOT QZP — cannot fix by cleanup)
1. **Lean `quality` gate is RED on main** because frontend (Angular/Karma) coverage = ~50% (statements 49.04%, branches 42.38%, lines 50%, functions 53.38%) vs a HARD 100% global threshold hard-coded in frontend/karma.conf.cjs. Backend passes 100%. Evidence: run 28200499746 log "Coverage ... does not meet global threshold (100%)" + exit 1. Reframe genuinely hit 100%; momentstudio has real ~10k-statement coverage debt. NOT fixable in this task; needs thousands of frontend tests (dev work).
2. **Alerts are real**: 87 open dependabot (18 high/53 med/16 low) + 119 open CodeQL code-scanning (1 crit/2 high/116 unrated). Require real dep upgrades + code fixes, not QZP retirement.
3. **9 genuine dependabot PRs left open** (#615,#614,#613,#599,#598,#562,#550,#547,#538): cannot merge green (red quality gate, unrelated to the bumps); rails forbid merging red / force-push. Left open + reported (not closed — they're not superseded/unworkable, just blocked).

## Verdict: momentstudio is NOT truly-green-able by the tanksflashmobile recipe. The QZP retirement + cleanup is done correctly, but the lean gate has a legitimate failing condition (frontend coverage) + real security alerts that are out of scope. Did NOT fake green by lowering the threshold or force-merging red (would violate the Reframe standard + rails).
