---
title: 'Fleet lean gate round-6 (final): self-contained lint; full program state (2026-06-18)'
type: note
permalink: main/projects/reframe/fleet-lean-gate-round-6-final-self-contained-lint-full-program-state-2026-06-18
tags:
- qzt
- fleet
- lean-gate
- round6
- reframe
- builds
- milestone
---

# Fleet round-6 (final template) + full program state (2026-06-18)

Continues [[fleet-lean-gate-rounds-4-5-basedpyright-standard-setup-dotnet-coverage-defer-repos-2026-06-18]].

## Rounds 1-5 MERGED, v1=1683d5dc. Round-5 sweep: basedpyright now 0 errors (standard mode works), BUT the real residual failure is the SEPARATE `gate-lint-format-secrets` step running the CALLER's `pre-commit run --all-files` — depends on each repo's bespoke hooks/env (npm ci needs root lockfile [momentstudio nested frontend], dotnet SDK [codex], caller-local eslint/tsc). The watcher's "FAIL@gate-types basedpyright" step-name was MISLEADING (basedpyright passed; the next step failed).
## ROUND-6 (wf_80dd92f7, FINAL template round): make gate-lint-format-secrets SELF-CONTAINED — drop caller `pre-commit run --all-files`; run lean tools directly: ruff check + ruff format --check (Python, honor caller [tool.ruff]) + gitleaks. oxlint+biome already self-contained in gate-types. Removes the entire caller-environment dependency class in one change. NOT weakening (same charter tools, enforced consistently). Confident this is the last template round (it eliminates the caller-bespoke-pre-commit failure class; remaining failures after = REAL repo coverage/lint = TDD/per-repo).

## Fleet green @final-v1 (pre round-6): 3/10 non-TDD green (env-inspector, personal-finance, star-wars); the other 7 (codex/devextreme/event-link/momentstudio/pbinfo/swfoc/tanks) fail at caller-pre-commit -> round-6 should clear most. 3 TDD repos (airline/codeblocks/webcoder) separate.

## NEXT after round-6 GO: admin-merge + move v1 -> rerun all -> merge greens + ATOMIC ruleset context flip (SaaS->quality, required⊆enabled) per green repo -> then STOP fleet template iteration (residual = real per-repo coverage/lint, documented).

## REFRAME BUILDS RUNNING (user: build 4 bundles metaswarm-orchestrated):
- Director v1 build (wf_bd232ead): 10 WUs, 5 waves, 4-phase, feat/director-v1.
- Repurpose+Editing-refine+UX/QoL build (wf_49eac0f2): 3 bundles parallel, sequential-within, 4-phase. Branches feat/repurpose-design, feat/editing-refine-design, feat/ux-qol-design.
- Intelligence: re-gate ALL CLEAR (build-ready, NOT in this build wave — user picked the other 4; queued for a future wave).
- 3-repo fleet TDD (wf_93d08c20): webcoder/airline/codeblocks -> 100% (multi-pass expected).
- Each feature build -> full-gate verify -> PR. MERGE the 4 feature PRs SEQUENTIALLY resolving handlers.register_all conflicts (the one shared file).

## DONE: Reframe Hub MVP(#213)+SECURITY(#214)+preview-fix(#215) merged, 0 issues/PRs. QZT 0 issues, #154 retired. Disk 0->111GB. 5 feature plans gate-clean. Formatter-before-commit baked into all build agents [[reframe-quality-gate-build-agents-must-run-formatters-not-just-linters]].

## ANTI-RABBIT-HOLE NOTE: 6 template rounds is a lot; each fixed a real general gap the varied fleet surfaced (cache/osv/tsc/biome/holes/nested-cov/no-unmatched/basedpyright/toolchains/self-contained-lint). After round-6, STOP template iteration — remaining non-green = real per-repo work (coverage via TDD, or genuine ruff/lint), handle per-repo or document. Prioritize the Reframe feature builds (higher value).