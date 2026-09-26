---
name: Fleet drive-to-zero worklist (2026-06-01 Phase-1 ground truth)
description: Per-repo×platform worklist + operator blockers for driving all 15 governed
  repos to absolute-0 + 100% coverage. Read at campaign resume.
type: project
permalink: main/claude-memory/documents-git-hub-quality-zero-platform/fleet-drive-to-zero-worklist
---

Phase-1 read-only enumeration (workflow wf_81cc89d3, 19 agents). See
[[truthful_gate_subsystem]]. Campaign decisions + canary in `.beads/plans/active-plan.md`.

## 🔴 URGENT SECURITY — operator rotate NOW (live exposed secrets, secret-scanning OPEN)
- **Personal-Finance-Management**: live **Google API key** exposed — rotate immediately.
- **WebCoder**: leaked **Microsoft Azure Entra ID token** — rotate immediately.
(Quality Secrets Preflight only checks CI-secret PRESENCE, so these are silently un-gated.)

## ✅ CANARY RE-DIAGNOSED (wf_6425998f, REAL CI logs) — code-fixable, NO operator tokens
All 3 gates fixable in code with existing tokens (fix build wf_6abd6a91 in flight on #236 branch):
- **Codacy publish**: step wires only empty CODACY_PROJECT_TOKEN; reporter aborts "project or account API token must be provided". FIX = add `api-token: secrets.CODACY_API_TOKEN` (already valid — Codacy Zero passes same run). 1-line.
- **Sentry Zero**: 401 is from the LEGACY project-slug endpoint `/projects/{org}/{project}/issues/`; token created 2026-03-10 NEVER rotated. FIX = migrate check_sentry_zero.py to org-scoped `/organizations/{org}/issues/` (same endpoint truth/preflight.py uses). Residual: org-endpoint token validity confirmed only by the post-fix gate re-run.
- **DeepScan Zero**: NOT a token — DeepScan App posts its check on PR head, never the squash-merge commit → absent on main. FIX = PR-head status fallback in check_deepscan_zero.py + `pull-requests: read` perm.

## Operator checklist COLLAPSED → only these remain:
1. 🔴 Rotate 2 exposed secrets (Google key in PFM, Azure token in WebCoder).
2. DeepSource dashboard: auto-commit OFF (autofix bot).
3. SonarCloud Auto-Analysis OFF on momentstudio/SWFOC/WebCoder.
(No token provisioning/rotation needed for the canary — collapsed.)

## (historical) Canary (PR #236 / platform) — initial inferred-as-token; superseded by re-diagnosis above
- Coverage 100 Gate fails at **Publish Codacy coverage**: `CODACY_PROJECT_TOKEN` empty
  (only CODACY_API_TOKEN exists). Fix: `gh secret set CODACY_PROJECT_TOKEN -R Prekzursil/quality-zero-platform`. Workflow already wires it (reusable-scanner-matrix.yml:591).
- Sentry Zero fails: `SENTRY_AUTH_TOKEN` **HTTP 401** (dead/rotated, not debt). Mint fresh (org `andrei-visalon`, read scopes) + update secret.
- DeepScan Zero (also red on platform main + env-inspector): missing/rotated `DEEPSCAN_API_TOKEN`.

## ⚠️ USER OVERRIDE 2026-06-01: do NOT rotate SENTRY_AUTH_TOKEN or DEEPSCAN_API_TOKEN — KEEP them.
The Phase-1 "401 = dead token" was INFERRED (subagent couldn't read the CI log), now invalidated by the
user. Tokens are valid → the Sentry Zero / DeepScan Zero failures are a CONFIG/PROBE issue or REAL
findings, fixable in CODE/config (or by resolving findings), NEVER by rotation. Re-diagnose against the
ACTUAL CI error. Also re-check: can the Codacy coverage publish use the EXISTING CODACY_API_TOKEN via
config (avoid provisioning a new CODACY_PROJECT_TOKEN)? → would make #236 code-fixable, no operator token.

## Operator-only blockers (Claude CANNOT do these) — REVISED
1. ~~rotate Sentry/DeepScan~~ — KEEP (user). Fix gates via config/findings instead.
2. CODACY_PROJECT_TOKEN — TRY config fix to reuse existing CODACY_API_TOKEN first; only ask operator if impossible.
4. DeepSource dashboard: toggle OFF "auto-commit to PRs" for deepsource-autofix bot (editing .deepsource.toml is a NO-OP — zero repos have [[transformers]]; it's a server-side org-app setting). Or revoke its contents:write via ruleset.
5. SonarCloud: disable Auto-Analysis on **momentstudio, SWFOC-Mod-Menu, WebCoder** (Auto-Analysis-vs-CI conflict).
6. Provision `DRIFT_SYNC_PAT` for fleet-wide sync propagation.
7. ROTATE the 2 exposed secrets (above).
8. Merge approvals (PRs).

## Fleet worklist (priority order)
| Repo | Effort | State / work |
|---|---|---|
| quality-zero-platform | large | FIX FIRST (control plane). 3 red gates token-fixable + ~2064 audit-masked real issues (838 Codacy/1116 DeepSource/110 Sonar). audit-mode masks them. |
| event-link | small | **CLEAN** — only Dependabot bumps (PRs #137/#138 open). |
| Airline-Reservations-System | small | **CLEAN** — stale 2026-04-28 aggregate gate; 1 trivial commit flips it; 1 vitest dep mid-fix. |
| DevExtreme-Filter-Go-Language | small | **CLEAN** — merge PR #32 (lint + drop committed tests.exe/test_output.log). |
| env-inspector | small | Codacy Zero + DeepScan Zero red (same DeepScan token sweep). GitHub-native 0, cov 100. |
| codeblocks-pretty-prints-stable | small | Codacy Zero only; ~21 .py; cov 100. |
| Star-Wars-GB-Save-Editor | medium | GitHub-native 0; coverage (Tkinter GUI), Codacy Zero, QLTY Zero; 3 modules. |
| codex-session-manager | medium | cov 100 GREEN. 158 CodeQL = **148× one rule (cs/path-combine, note-sev)** → single sweep. + Sonar/Codacy/DeepScan backlogs. |
| pbinfo-get-unsolved | medium | DeepSource JS/Python drift (scanner not in profile — reconcile). 14 CS (1 crit py/partial-ssrf), 1 high Dependabot. |
| Reframe | large | 4 red gates; 45 Dependabot (3c/22h); 37 open PRs; Rust branch-100 + cov-merge gap. |
| SWFOC-Mod-Menu | large | 7 red gates; 264 CodeQL; cov climbing (PR #137 84.8%→100); Sonar auto-analysis; multi-lang. |
| TanksFlashMobile | large | ~10 red; 77 Dependabot; **NO coverage tooling** (smoke-only, TS/GDScript/Kotlin/Swift); secrets missing; 32 PRs. |
| momentstudio | large | 7/12 gates red; 628 CodeQL + 61 Dependabot; visual gates; Sonar auto-analysis; 15 PRs. |
| Personal-Finance-Management | large + 🔴SEC | exposed Google key; 7 red; 76 CodeQL (1err/9h); JaCoCo not applied + ZERO test sources. |
| WebCoder | large + 🔴SEC | leaked Azure token; committed backend/venv/ (8724 blobs) poisons CS+coverage — **purge first**; 9 red; 104 Dependabot; 83 CS; 32 PRs. |

## Progress (no-token PRs, awaiting operator merge)
- ✅ WebCoder **PR #78** OPEN — purged `backend/venv/` (8724 files; 8955→231 tracked). Azure token NOT in venv (rotate separately).
- ✅ codex-session-manager **PR #64** OPEN — Path.Combine→Path.Join, clears **148/158 CodeQL** (cs/path-combine). dotnet build 0 err, 113 tests pass (+1 null-guard), cov neutral. 10 heterogeneous alerts left for operator (catch-all-exc/dispose-on-throw/missed-select/local-not-disposed).
- ⏳ Canary re-diagnosis (wf_6425998f) — Sentry/DeepScan/Codacy real-error + token-preserving fix (tokens KEPT).

## Claude-doable NOW without operator tokens (code-side, PRs for user merge)
- WebCoder: purge `backend/venv/` (security surface + coverage denominator). ✅ PR #78
- codex-session-manager: sweep the 148× cs/path-combine CodeQL rule.
- DevExtreme #32, event-link #137/#138: review/advance for merge.
- Airline: trivial commit to flip stale aggregate gate.

## STRATEGY (user 2026-06-01): LEVERAGE, not brute-force
Knock out max findings with least effort: (1) dominant-rule bulk transforms (codex 148× Path.Combine→Path.Join =
PR #64), (2) native autofix/formatters (ruff/eslint/gofmt/dotnet-format/clang-format/cargo --fix, behavior-preserving),
(3) generated/vendored/binary exclusions (WebCoder venv = PR #78), (4) dependabot GROUPING config (dozens→few PRs).
Always build/test-verify before PR; report honestly if unverifiable (never ship broken mass-edits).

## CANARY #236 RESULT (2026-06-05, fixes on 9b18dec/fefcc64)
- ✅ Coverage 100 Gate GREEN — Codacy `api-token: secrets.CODACY_API_TOKEN` fix worked (no project token needed).
- ✅ DeepScan Zero GREEN — PR-head status fallback worked.
- ❌ Sentry Zero STILL 401 on the ORG endpoint too (migration deployed). Token created 2026-03-10, never rotated; passed in #225 (Apr), 401s on both project+org endpoints now → **token EXPIRED/REVOKED** despite user "keep it". CONFLICT surfaced to user. No non-rotation fix exists (truthful gate correctly red on unreadable token). Sentry Zero blocked on user providing a working token; everything else proceeds.
- Autofix bot churns every push (9b18dec→86d2056→ffe7788→419dcf3) — recommend operator disable auto-commit.

## FAN-OUT RESULT (wf_5ddc03ed, 7 PRs, ~226 alerts on merge)
momentstudio #576 (5; 594 Alembic = FALSE-POS, not edited), SWFOC #172 (**197**! cs/useless-upcast 95 + path-combine 80 + cast-to-self 22, all test code, build+3904 tests green), Reframe #191 (2), TanksFlashMobile #131 (1), PFM #30 (2), WebCoder #79 (16), pbinfo #15 (3). env-inspector/codeblocks/Star-Wars-GB already clean (no PR).
NEXT LEVERS: (1) Dependabot grouped merges ~287 (operator), (2) CodeQL paths-ignore for generated/migration code (momentstudio 594 Alembic) OR bulk-dismiss-FP, (3) merge #78 (33 venv alerts), (4) dismiss ~20 confirmed FPs (SWFOC 11 load-bearing casts, momentstudio 6 caches, Reframe 2 SQL-IS-NULL, Tanks 1 stale).
COVERAGE BUILD-SETUP (real eng): PFM (JaCoCo+AndroidSDK+write tests from 0), TanksFlashMobile (no cov tooling).

## FP DISMISSALS DONE (2026-06-05, 602 alerts; gh PAT has code-scanning write)
momentstudio 599 (594 Alembic + 5 caches; open CodeQL 628→29), Reframe 2 (py/test-equals-none), Tanks 1 (stale unpinned-tag).
- SKIPPED momentstudio #921 `_IPAddress` (dependencies.py) — referenced NOWHERE → likely TRUE dead type alias, needs real fix/removal not dismiss.
- SWFOC 11 keep-FPs: DEFERRED — dismiss AFTER PR #172 merges (can't distinguish from the 95 to-be-fixed while 81 open).
RESIDUAL no-token CodeQL to fix-or-report: momentstudio 29 (ineffectual-stmt/multiple-def/path-injection/full-ssrf/cyclic-import/js-useless-assign), pbinfo 14 (1 crit py/partial-ssrf), WebCoder ~34, PFM ~74 (1 err/9 high), Reframe residual. Star-Wars-GB coverage 98/99%→100 (Tkinter partial branches).

## In-flight workflows (2026-06-01)
- canary-fix (wf_6abd6a91): 3 token-preserving platform fixes on #236 branch (Codacy api-token / Sentry org-endpoint / DeepScan PR-head).
- leveraged-fix fan-out (wf_5ddc03ed): 10 consumer repos — autofix + dominant-rule + dependabot-grouping + exclusions, PR-or-report.

## Biggest risks
- Misreading token-failures (Sentry 401 / Codacy empty-token / DeepScan) as real debt → wasted remediation.
- DeepSource autofix force-push race (data-loss on concurrent pushes) until gated.
- audit-mode green ≠ clean on platform (~2064 masked).
- Coverage structural gaps: PFM (no tests/JaCoCo), TanksFlashMobile (no cov tooling) = build tasks not test-writing.