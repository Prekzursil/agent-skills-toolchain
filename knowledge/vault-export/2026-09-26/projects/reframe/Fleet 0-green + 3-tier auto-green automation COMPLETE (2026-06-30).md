---
title: Fleet 0-green + 3-tier auto-green automation COMPLETE (2026-06-30)
type: note
permalink: main/projects/reframe/fleet-0-green-3-tier-auto-green-automation-complete-2026-06-30
tags:
- fleet
- zero-green
- automation
- dependabot
- github-models
- copilot
- qzp
---

# Fleet 0-green + auto-green automation DONE (2026-06-30)

User: "resume repo only 0 green fleet" + "automatization of github copilot (agents, codex)". Drove the owned-repo fleet to 0-green AND installed a 3-tier auto-green automation per repo.

## RESULT — 6/6 repos-needing-work GREEN + automated (rest of ~20 owned already green)
- **agent-skills-toolchain** — fixed a REAL latent bug: gitleaks-action@v2 needed GITHUB_TOKEN to scan pull_request events (push worked so main looked green, but PR scans/auto-merge were broken). + automation.
- **bilbo-app** ✅ (note: #91/#94 = genuine upstream constraints — Kotlin-metadata lag, API-37 beta — reopen weekly until upstream clears, won't auto-merge while red).
- **codeblocks-pretty-prints-stable** ✅ (only 1 PR really open; #24/#25 already merged).
- **grace-iberlef-2026** ✅
- **codex-session-manager** ✅ (#76-79 merged; died once on transient connection-close, re-ran clean).
- **opus-bulk-downloader** ✅ (the "CANCELLED" runs were Dependabot service jobs, not project CI; quality green).

## 3-TIER AUTOMATION (user-chosen: "do 1 [Models] and 2 [Copilot] when needed not wasteful")
- **Tier1 — Dependabot auto-merge** (free, native): .github/workflows/dependabot-auto-merge.yml (pull_request_target, actor==dependabot[bot], gh pr merge --auto --squash, gated on required checks) + allow_auto_merge=true. Kills patch/minor drift.
- **Tier2 — GitHub Models autofix** (free, in-Actions, PRIMARY auto-fix): .github/workflows/autofix-models.yml — on workflow_run failure (quality/CodeQL) or new alert, GitHub Models (openai/gpt-4o-mini via ai-inference) drafts a fix → opens a LABELED 'autofix' DRAFT PR, NEVER auto-merged (human/CI gates). Verified it SKIPS on green runs.
- **Tier3 — Copilot coding agent** (student sub, JUDICIOUS): documented escalation (.github/AUTOMATION.md or README) — assign @copilot to a stuck failing-check issue ONLY when Tier2 can't fix (premium requests finite; NOT wired to fire on every failure).
RAILS held: REAL fixes only, no thresholds lowered, no force-merge-red, no --no-verify, scoped commits, disk-hygiene.

## REMAINING fleet item: momentstudio (the one repo with genuine work)
Lint gate GREEN (fixed). Coverage = the last gate: admin.component.ts 396 uncovered branch-arms (370 lines, 8 chunks) + shop:2425 + product-card:645. Surgical coverage workflow wqayn000p running (8 writers w/ exact line lists → focused-admin verify → full gate via longrun → cov→main + merge train #617/#614/#615/#616/#620/#538). Relates [[qzp-heavy-lean-migration-audit-gated-plan-2026-06-29]] (the QZP governor would orchestrate this fleet-wide; this is the manual drive + automation seeds).
