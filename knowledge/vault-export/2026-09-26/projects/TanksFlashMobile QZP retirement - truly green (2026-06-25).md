---
title: TanksFlashMobile QZP retirement -> truly green (2026-06-25)
type: note
permalink: main/projects/tanks-flash-mobile-qzp-retirement-truly-green-2026-06-25
tags:
- tanksflashmobile
- qzp
- ci
- github
- green
---

# TanksFlashMobile -> truly green (mirror Reframe)

Task: retire QZP "Quality Zero" SaaS machinery; lean `quality` gate is the real required check.

## DONE
- Disabled 14 QZP/SaaS/churn workflows (Quality Zero Gate/Platform/Backlog/Remediation, strict-21 Preflight, KPI/Release-Steward/Branch-Protection/Curation digests, Codecov/Applitools/Chromatic, Agent Task Queue/Label Sync).
- Disabled the active `quality-zero-platform` ruleset (Reframe's is disabled) -> only classic branch protection requires `quality / quality` + `codeql / CodeQL`.
- PR #158 MERGED: deleted retired workflow .yml + scripts/quality/* + codecov.yml. KEPT .quality/opengrep (used by lean gate).
- Closed 74 issues (all QZP artifacts incl human-authored strict-23 blockers #22/#23) with "Superseded: QZP retired; migrated to the lean quality gate."
- Closed 7 superseded non-dependabot PRs (#28,#36,#131,#132,#133,#134,#135).
- KEY FINDING: ci.yml/ci-fast.yml ("Web build + smoke") used prettier (space indent) which PERMANENTLY conflicts with lean gate's oxlint+biome (tab indent) -> can never be green alongside required gate. Reframe has NO prettier CI. So closed prettier-reformatting PR #162 and instead retired ci.yml+ci-fast.yml via PR #163 (MERGED). Active workflows now = Reframe shape: quality, codeql x2, release, dependabot, copilot.
- main HEAD quality = success.
- Code-scanning: dismissed stale #27 (sonar-zero.yml gone) + #33 (SonarCloud retired). #28 (check_codacy_zero.py) auto-resolves on #158 (file deleted). 0 dependabot alerts.

## IN PROGRESS
- 8 dependabot PRs being rebased/recreated onto new main (#54,#55,#156,#159,#160,#161 rebase; #47,#49 recreate multi-dir groups). Merge green, close unworkable. Goal 0 PRs.

## Gotchas
- gh workflow disable does NOT delete file; delete in PR.
- core.autocrlf=true on Windows -> set false before prettier to avoid CRLF churn (moot now, prettier path abandoned).
- biome (lean gate) vs prettier (old CI) indentation conflict is irreconcilable -> retire the prettier CI, don't reformat.
