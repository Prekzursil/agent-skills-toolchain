---
title: 'webcoder lean-gate: frontend 100% DONE; basedpyright blocked on template bug
  + backend scope (2026-06-20)'
type: note
permalink: main/projects/reframe/webcoder-lean-gate-frontend-100-done-basedpyright-blocked-on-template-bug-backend-scope-2026-06-20
tags:
- webcoder
- lean-quality-gate
- coverage
- basedpyright
- fleet
---

# webcoder feat/lean-quality-gate continuation (2026-06-20)

Continued from round-6. Branch `feat/lean-quality-gate`, repo moved to Prekzursil/WebCoder. Worked in fresh Windows temp clone.

## DONE — Frontend TS coverage now 100% (the deliverable)
- Full frontend (`frontend/webcoder_ui`) = **100% line/branch/func/stmt, 235 tests, 25 suites** (CRA `react-scripts test --coverage`, jest threshold 100).
- Covered the 2 remaining real components:
  - **ProblemDetailPage.tsx** → 100% (17 tests). istanbul-ignore on 2 truly-unreachable submit guards (`!auth.token` is dead since `isAuthenticated===!!token` and form only renders when authed; `!selectedLanguage` dead since it always defaults python3).
  - **ProblemFormPage.tsx** → 100% (33 tests). **Found+fixed a REAL bug**: edit-mode load `.then()` never reset `isLoadingData` → spinner forever on successful edit load. Fix = `.finally(() => setIsLoadingData(false))`.
- `src/types/{api,index}.ts` (0% cov) = pure type-only files (no runtime decls, grep-confirmed) → added `!src/types/**/*.ts` to jest collectCoverageFrom (reasoned exclude, not weakening).

## Gate fixes pushed (commits bc9302b..d6dd164, all on origin)
1. ProblemDetailPage + ProblemFormPage tests/fix
2. type-only coverage exclude
3. **oxlint `--deny-warnings`** (gate uses oxlint@1.69.0 --deny-warnings — local oxlint w/o flag MISSES these): removed 4 pre-existing unused test imports (act/fireEvent/waitFor).
4. **biome 2.5.0 format**: ran `biome format --write frontend/webcoder_ui/src` — round-6's format commit drifted vs biome 2.5.0 (lineWidth-100 rewrap). GOTCHA: `git archive` on Windows injects CRLF → false biome-ci failures; trust working-tree `biome ci` (clean) + committed blob LF (`git cat-file -p|grep -c $'\r'`=0), not archive.
5. **ruff** (gate `ruff check . && ruff format --check .`): `# noqa: E402` on 4 `scripts/quality/check_*_zero.py` path-insert-then-import lines (legit pattern) + `ruff format` 8 pre-existing-drift script files.
6. **tsc** (gate `tsc -p frontend/webcoder_ui/tsconfig.json --noEmit`, isolatedModules): `index.test.tsx` had no top-level import/export → added `export {};` (TS1208).

Gates now GREEN: gate-lint-format-jsts, gate-lint-format-py, gate-types tsc.

## BLOCKED — gate-types basedpyright (NOT fixable in webcoder, out of frontend scope)
- **Template BUG**: `quality-zero-platform/.github/workflows/reusable-quality.yml@v1` runs `basedpyright --typecheckingmode standard` → basedpyright 1.39.8 rejects it ("Unexpected option --typecheckingmode", exit 4). Correct CLI has NO such flag (only `--level`, config-file `typeCheckingMode`). **Fix belongs in the template repo**, not webcoder.
- Webcoder-side workaround = ship `basedpyrightconfig.json` (template then runs bare `basedpyright`). BUT that triggers full backend type-check = **141 errors + 2107 warnings** on the Django backend (46 .py files, no type stubs). That's a multi-day backend annotation effort, NOT frontend coverage.
- Downstream gates (gate-tests-coverage jsts/python, sast, secrets, deps) never reached — blocked behind basedpyright.

## Recommendation
- Frontend coverage objective COMPLETE + pushed. 
- To get full gate green: (a) fix the `--typecheckingmode` flag in the quality-zero-platform template (tag a v1 fix), AND (b) a separate backend basedpyright remediation pass (or ship a relaxed `basedpyrightconfig.json` — user decision, since "standard" was the charter intent).
