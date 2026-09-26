---
title: event-link lean-quality-gate fixes (2026-06-20)
type: report
permalink: main/projects/event-link-lean-quality-gate-fixes-2026-06-20
tags:
- event-link
- lean-quality-gate
- basedpyright
- coverage
- osv
---

# event-link lean-quality-gate drive to green (2026-06-20)

Branch `feat/lean-quality-gate`, PR#140. Lean gate = Prekzursil/quality-zero-platform reusable-quality.yml@v1 (single job, auto-detect langs). Worked in temp clone.

## Root causes found (each was a real CI failure, not what it first looked like)
- **basedpyright gate failed on `Unexpected option --typecheckingmode`** (exit 4), NOT real type errors. The pip basedpyright CLI rejects `--typecheckingmode`; only the npm CLI accepts it. The gate's fallback: if caller ships a pyright config, it runs bare `basedpyright` (no flag). FIX = ship `pyrightconfig.json` (NOT basedpyrightconfig.json — bare basedpyright auto-discovers pyrightconfig.json but NOT basedpyrightconfig.json on the pip CLI).
- **The gate runs basedpyright BEFORE installing app deps.** fastapi/sqlalchemy/pydantic/alembic ship inline types (not typeshed), so they're UNRESOLVABLE in the stub-only gate env → cascade `reportMissingImports` + `reportInvalidTypeForm` (Annotated[Session,Depends] aliases collapse to Unknown) + `reportAttributeAccessIssue`. Reference repo Reframe handles this via `reportMissingImports=warning` + exclude tests. event-link needed MORE: scoped `executionEnvironments` demoting reportInvalidTypeForm+reportAttributeAccessIssue to warning ONLY under backend/app + backend/alembic. Verified two ways: deps-INSTALLED basedpyright = 0 real errors (source of truth); deps-LESS = 0 errors + injected real error still FAILS.
- **GOTCHA: local basedpyright defaulted to system Python 3.14 which had deps globally installed → false 0-errors.** Must reproduce CI with `--pythonpath <clean-3.11-venv>/python.exe` (clean venv = only ruff+basedpyright).
- **Coverage gate detection is ROOT-only** (`git ls-files pyproject.toml pytest.ini ...`). Config was in backend/. FIX = root `pyproject.toml` (config-only, NO [project] table to avoid `pip install .`) with `[tool.pytest.ini_options]` pythonpath=[backend, backend/tests] + testpaths=[backend/tests] + `[tool.coverage.run] source`. Gate runs `python -m pytest --cov --cov-branch --cov-fail-under=100` from ROOT.
- **lizard test** hard-imports lizard (not in requirements.txt; gate installs only requirements.txt+pytest-cov) → `pytest.importorskip("lizard")` (coverage-neutral; it reads files via lizard, doesn't import app).
- **JS/TS coverage lane** needs a `test:coverage` script (or `vitest --coverage` literally in `test`). ui had only `test:unit:coverage` → added `test:coverage`. vitest already enforces 100% thresholds.
- **osv deps gate** had 58 CVEs. Fixed by UPGRADING (policy: no suppression): Python via `uv pip compile --upgrade` (starlette 0.49→1.3.1 + fastapi 0.121→0.138; cryptography/pyjwt/pydantic-settings/python-multipart/mako/idna) + regen contracts/openapi.json (fastapi adds ValidationError ctx/input). npm: axios/react-router-dom/vite/vitest bumps + overrides (esbuild/form-data/ws/@babel/core/js-yaml). **pytest pulls pygments transitively → osv flagged it → pin pygments==2.20.0.**
- **biome local CRLF false-positive**: core.autocrlf=true gave 197 "errors"; CI (LF) passes (prior run "194 files, 0 errors"). Verified LF copy passes.

## Type-fix patterns used (real, no blanket noqa/ignore)
TypeGuard for `_is_student_user`/`_online_learning_enabled_for_user`; @overload `_normalize_dt`; TypedDict for FastAPI dependency-dict returns + ro_universities (name Required); `Sequence[Row[tuple[...]]]` for SQLAlchemy `.all()` results; `cast(CursorResult[Any],...)` for `.rowcount`; `list[ColumnElement[bool]]` filters; `cast(Any, fake)` for deliberate test doubles; `setattr` for ModuleType monkeypatches; scoped `# pyright: ignore[reportMissingImports]` only for bcrypt/passlib/libcst (real deps, no gate stubs).

## Status at handoff
All gates GREEN locally under CI-faithful conditions. Commits ec82864 pushed. GitHub Actions had NOT dispatched the quality run for ec82864 after ~8min (dispatch backlog; prior df0045d runs still in_progress). Final `quality` CI conclusion = pending dispatch.
