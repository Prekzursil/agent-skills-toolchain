---
title: tanksflashmobile lean-quality-gate green (2026-06-20)
type: note
permalink: main/projects/tanksflashmobile-lean-quality-gate-green-2026-06-20
tags:
- tanksflashmobile
- lean-quality-gate
- ci
- coverage
- vitest
---

# tanksflashmobile lean-quality-gate -> FULLY GREEN (2026-06-20)

Repo: Prekzursil/TanksFlashMobile (renamed from tanksflashmobile). Branch feat/lean-quality-gate, PR #148 (draft). Drove the lean 6-gate `quality` CI (reusable Prekzursil/quality-zero-platform reusable-quality.yml@v1) to green. Final pushed SHA = 4bdde09; quality CI run 27858498326 = SUCCESS (all steps).

## What was actually failing vs already-green
- Gate 1 (ruff/ruff-format/oxlint/biome), Gate 2 (tsc per-app + basedpyright via pyrightconfig.json standard), Gate 4 (semgrep/opengrep .quality/opengrep), Gate 5 (gitleaks): already green.
- Gate 3 jsts coverage: FAILING (no root coverage runner; only Playwright .spec.ts existed). PRIMARY work.
- Gate 6 osv: FAILING (84 dev-dep CVEs).

## Key gotchas (durable)
1. **Windows autocrlf is a false-positive trap for biome.** `core.autocrlf=true` rewrites checked-out blobs to CRLF; biome (lineEnding:lf) then reports 30 files unformatted LOCALLY, but committed blobs are LF and Linux CI is clean. Fix: `git config core.autocrlf false; git config core.eol lf; git reset --hard` to mirror CI before running biome locally. Verify with `git show HEAD:<file> | grep -c $'\r'` (blob truth, not worktree).
2. **The lean gate runs jsts coverage in the ROOT dir only** (when a root package.json exists `proj_dirs=(.)`, it does NOT descend into apps/*). So the coverage runner must be a ROOT `test:coverage` script. Wired root vitest 3.2.6 + @vitest/coverage-v8 + jsdom + vitest.config.ts (jsdom env, v8, 100% thresholds, coverage.include scoped to the 7 unit-testable apps/web/src modules: config/debug/gamepad/i18n/input/touchControls/viewport).
3. **main.ts (1766-line browser bootstrap, no exports, top-level DOM wiring) and ruffle.d.ts are excluded from coverage** — integration/E2E surface covered by apps/web/e2e Playwright specs, documented in vitest.config.ts. Not weakening (not unit code).
4. **CRITICAL: the Python test-surface detection matches `tests/**` and `**/tests/**` REGARDLESS of file extension.** Putting TypeScript `tests/web/*.test.ts` there made the gate think Python had a test surface -> Python coverage lane FAILED ("source+tests but no coverage config"). Fix: put jsts suites under a NON-`tests` dir (used `vitest/`). The jsts detection is filename-based (`**/*.test.*`) so it still finds them. THIS bit me once on CI after a local-green push.
5. osv clean-zero = upgrade-first (npm update for transitive; `overrides` for esbuild 0.28.1 / storybook 8.6.17 / uuid 11.1.1; electron 40.2.1->40.8.5 direct). vitest pulls esbuild 0.27.7 -> needed root esbuild override too; vitest 3.2.4 itself had a CVE -> bumped to 3.2.6.
6. Branch-coverage to 100% required removing 2 genuinely-unreachable defensive dead branches (REAL fixes, not suppressions): input.ts dropped `if(!sources) return` (pressFrom keeps both maps in sync); gamepad.ts dropped redundant `supported?` ternary in tick (tick only runs when supported) and the redundant release loop in the disabled-tick branch (setEnabled(false) already releases).

## CI trigger note
quality.yml triggers on push:[main]/pull_request:[main]/workflow_dispatch. A push to the feature branch with an OPEN PR to main triggers a pull_request run; also dispatchable via `gh workflow run quality.yml --ref <branch>`. After the renamed-repo push, the auto pull_request run fired correctly.

73 real vitest tests, 100% line/branch/function/statement on the scoped modules.
