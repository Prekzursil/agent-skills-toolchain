---
title: Reframe quality-zero program (tracker)
type: project
permalink: main/projects/reframe/reframe-quality-zero-program-tracker
tags:
- reframe
- quality-zero
- ci
- coverage
- program-tracker
---

# Reframe quality-zero program (multi-session tracker)

GOAL (user, emphatic): `Prekzursil/Reframe` to **absolute zero issues on EVERY provider dashboard** (not just CI-caught), **100% line+branch coverage** everywhere accepted, **all 42 PRs reconciled+merged**, security alerts cleared, **main + every PR truly green**. Approach chosen: **full tracked milestone program, multi-session, parallelized**.

## Repos / worktrees / build env
- Reframe clone: `C:/Users/Prekzursil/Documents/GitHub/Reframe` (dirty, on chore/codacy-markdown-sweep). Reframe-fix clone too.
- QZT (control plane) clone: `C:/Users/Prekzursil/Documents/GitHub/quality-zero-platform` (main; push-PROTECTED → PRs only).
- Worktree `Reframe-electron` → branch `feat/desktop-electron-app` → **PR #200** (media-studio landed as apps/desktop-electron, additive).
- Worktree `Reframe-sonar` → branch `chore/sonar-zero-remediation` → **PR #201** (Sonar R1). **Build env PROVISIONED here**: `.venv` (api/worker reqs + pytest-cov) + `apps/web/node_modules` (npm ci). `tsc --noEmit` exit 0 (R1 TS compiles). Sonar issue worklist files gitignored: `_sonar-issues*.json`.
- QZT branch `chore/reframe-enforce-deepsource-qlty` → **PR #247** (adds DeepSource Visible Zero + QLTY Zero to reframe required checks via profiles/repos/reframe.yml + regenerated generated/rulesets/reframe.json).

## The 19 required gates (synced from QZT generated/rulesets/reframe.json; profile profiles/repos/reframe.yml; live ruleset id 14488874)
Per-gate TRUTH from #201 logs:
- **Sonar Zero**: branch issues = **0** (R1 cleared them) BUT fails on `Quality gate UNKNOWN / Sonar API 404` → SonarCloud PR-analysis/QG NOT running on PRs. INFRA.
- **Codacy Zero**: **1975 open issues** + duplication **15%** (goal ≤10%) + coverage missing. CODE (big).
- **QLTY Zero**: complexity — total 414; many-param/return/high-complexity fns (generate_shorts=25, _build_clip_subtitle_assets=10 params, _apply_groq_segment_scoring=6, etc.). CODE refactor.
- **Coverage 100 Gate**: reports EMPTY 0/0, branch data MISSING, no python xml → coverage GENERATION broken in CI. INFRA + then real 100%.
- **DeepSource: JavaScript + Python**: failing. CODE.
- **Quality Secrets Preflight / Chromatic Playwright / strict-23 #92**: all = **CHROMATIC_PROJECT_TOKEN blank in CI**. USER must set (token given in chat `chpt_e8b137b0dd5d817` — assistant CANNOT set secrets; user runs `gh secret set CHROMATIC_PROJECT_TOKEN --repo Prekzursil/Reframe --body <tok>`; ROTATE after, it's chat-exposed; check Environment-vs-repo scope).
- Codecov Analytics, Applitools Visual, Node dep audit: failing (coverage/visual/dep).
- PASS: Python API & worker checks, Web build, DeepScan, CodeRabbit, BrowserStack, most DeepSource langs.

## Local test-run finding (env gaps, not proof of broken code)
Provisioned-local run: python 101 passed / **43 errors** (all media-core INTEGRATION tests needing full app + test DB/fixtures my quick provision lacks) + 3 failed; web 10 failed (`localStorage.removeItem is not a function` in App.usage.test.tsx — test-harness/mock, R1 only touched App.tsx source). So coverage is currently UNMEASURABLE until the test/coverage pipeline runs clean (best fixed IN CI with real env).

## Round plan (drive in order; report dashboard counts each round)
1. **R-INFRA** (FIRST — makes progress measurable): (a) get SonarCloud PR-analysis running so Sonar Zero gets a QG (investigate the sonar-scan workflow/condition; maybe SonarCloud project PR config); (b) repair coverage GENERATION (codecov-analytics workflow runs profile coverage.command → emits 0/0; get real lcov+xml incl. python + branch); (c) get test suites running clean (the 43 py integration errors need the CI DB/env; web localStorage mock); (d) USER: Chromatic token. 
2. **R-CODE** (orchestrate, build env ready): Codacy 1975 (mostly pylint: missing-docstring C0114-116, line-too-long C0301, too-many-args/branches/locals → docstrings+format+refactor) + duplication 15%→<10% + qlty complexity + DeepSource JS+Py → true zero. Providers OVERLAP (same linters) → fixing cascades.
3. **R-COV**: real 100% line+branch across apps/api, services/worker, packages/media-core, apps/web, apps/desktop (after R-INFRA tests run clean).
4. **R-MERGE**: 42 PRs — 36 dependabot (auto-merge once gates green; clears 48 security alerts) + substantive #192(CodeQL)/#196(mdlint)/#191(QZP)/#193(ECC) + conflicts #114/#107 (big coverage/desktop feature). Then media-studio #200 + QZT #247.

## Key lessons
- Sonar PR-scope = NEW-code only (showed 0); *Zero gates count OVERALL + QG status. Authoritative per-provider worklist = the #201 `*Zero` check LOGS (gh api actions/jobs/<id>/logs), not the public issues API.
- Disjoint per-file agents can break cross-file contracts (R1: shorts.py dropped `provider` param flagged S1172-unused, but worker.py:2098 passed it → fixed by dropping the caller arg). Verify cross-file callers.
- Secrets present in Reframe (Sonar/Codacy/Codecov/Snyk/Sentry/DeepScan/Tauri) EXCEPT Chromatic blank.
- assistant cannot: set CI secrets, change SonarCloud/Codacy/Codecov DASHBOARD settings → surface these for the user.


## ROUND 1 (R-INFRA) progress — 2026-06-15
- ✅ **Web test infra FIXED** (commit b958f78 on chore/sonar-zero-remediation, pushed): jsdom-under-vitest4 exposed an incomplete Storage (no removeItem) → every auth-resetting test crashed in beforeEach (PRE-EXISTING on main, not R1). Added a complete in-memory localStorage/sessionStorage to apps/web/src/test/setup.ts. Result: web suite 47/47 pass; **v8 coverage = 100% line+branch+func+stmt**; lcov.info generates with branch records (BRF/BRH). This unblocks the web half of Coverage 100 Gate (was 0/0 only because tests failed).
- ℹ️ **43 Python "errors" = Windows-LOCAL-ONLY bug, NOT real**: apps/api/tests/conftest.py:42 builds `sqlite:////{str(db_path).lstrip('/')}` — fine on Linux/CI, malformed with a Windows drive letter → 'unable to open database file'. CI (ubuntu) runs them fine. So Python tests are NOT a real blocker; do NOT 'fix' the conftest for Windows (it's correct for CI). I just can't run the API/integration tests locally on Windows.
- ℹ️ **Coverage 100 Gate inputs = web + desktop-ts lcov ONLY** (profile coverage.inputs); python-coverage.xml feeds Sonar, not this gate. So the gate needs web (DONE) + desktop-ts (apps/desktop Tauri — NOT yet verified) at 100%.
- ℹ️ Chromatic token: USER set it. Validates on next CI run (push of b958f78 triggers it).
- ℹ️ apps/web vite.config coverage EXCLUDES App.tsx, api/client.ts, SettingsModal, ErrorBoundary, subtitles/**, shorts/** → 100% targets the remaining files (tractable).

### NEXT (round 2): read #201 fresh CI after b958f78 push (web cov + Chromatic/Secrets should improve). Then: (a) verify/fix apps/desktop (desktop-ts) tests+coverage→100; (b) SonarCloud PR-analysis not running (Sonar Zero 404) — investigate the sonar-scan workflow trigger / SonarCloud project PR config; (c) THEN code grind: Codacy 1975 + dup 15% + qlty complexity + DeepSource. Build env still provisioned in Reframe-sonar (.venv + apps/web/node_modules).