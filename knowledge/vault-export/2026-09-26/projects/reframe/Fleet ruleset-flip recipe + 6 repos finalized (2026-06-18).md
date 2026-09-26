---
title: Fleet ruleset-flip recipe + 6 repos finalized (2026-06-18)
type: note
permalink: main/projects/reframe/fleet-ruleset-flip-recipe-6-repos-finalized-2026-06-18
tags:
- qzt
- fleet
- lean-gate
- ruleset
- branch-protection
- recipe
- milestone
---

# Fleet finalization: ruleset-flip recipe + 6 repos done (2026-06-18)

Continues [[fleet-lean-gate-round-6-final-self-contained-lint-full-program-state-2026-06-18]]. Template complete (6 rounds, v1=b9503300). 6/13 repos GREEN on the lean gate -> FINALIZED (merged + contexts flipped).

## ✅ FINALIZED (merged to main + lean contexts): airline, codex-session-manager, devextreme, env-inspector, personal-finance, star-wars.

## THE FLIP RECIPE (lean end-state = required checks: `quality / quality` + `codeql / CodeQL`, all SaaS removed):
- Lean check context = **`quality / quality`** (workflow name `quality`, job `quality`). codeql = `codeql / CodeQL`. Both green = the only required checks.
- A repo can be gated by TWO mechanisms — fix BOTH:
  1. **Ruleset** (`gh api repos/O/R/rulesets/<id>`): GET, in node filter required_status_checks to drop SaaS (regex `/shared-scanner-matrix|shared-codecov-analytics|qlty|sonar|codacy|deepsource|deepscan|aggregate-gate|quality rollup|quality zero/i`) + ensure `quality / quality`; PUT back the FULL body {name,target,enforcement,conditions,rules,bypass_actors}. (Keeps real native checks like codex build-test/scan/dependency-review.)
  2. **Classic branch protection** (`gh api -X PATCH repos/O/R/branches/main/protection/required_status_checks --input {"contexts":["quality / quality","codeql / CodeQL"]}`) — some repos (devextreme/personal-finance/star-wars) ALSO have this; the ruleset flip alone won't unblock them.
- Many fleet PRs are DRAFTS -> `gh pr ready` before merge. Merge method: linear-history repos need `--squash`. Residual `mergeState=BLOCKED` with contexts-satisfied+not-behind+no-review -> `gh pr merge --admin --squash` (lean gate genuinely green; admin override safe).
- GOTCHA: node `/tmp` = C:\tmp\ but bash `/tmp` = %LOCALAPPDATA%\Temp -> write ruleset JSON to an ABSOLUTE C: path (e.g. /c/Users/Prekzursil/_rs.json + "C:/Users/Prekzursil/_rs.json") so both agree.

## 🔄 STILL RUNNING: drive-to-green (wf_f55e8157) for the 7 red (codeblocks/pbinfo/swfoc py-coverage; tanks jsts-coverage; event-link/momentstudio/webcoder basedpyright) — real test/type work. When each goes green, finalize with the recipe above. Reframe feature builds continuation (wf_f4297f8d): Director remaining + Repurpose/Editing/UX remaining WUs.

## TODO after all 13 green: flip QZT's OWN ruleset (still has SaaS required) + delete the QZT SaaS machinery (runbook final step) once no repo references the old shared workflows.