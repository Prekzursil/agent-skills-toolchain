---
title: 'momentstudio lean-quality-gate: basedpyright+gitleaks green, coverage gap
  62%'
type: note
permalink: main/projects/momentstudio-lean-quality-gate-basedpyright-gitleaks-green-coverage-gap-62
tags:
- momentstudio
- lean-quality-gate
- basedpyright
- coverage
- ci
---

# momentstudio feat/lean-quality-gate (2026-06-20)

Lean gate = reusable Prekzursil/quality-zero-platform reusable-quality.yml@v1. Single sequential job; `set -e` means first failing gate ABORTS and later gates show "skipped" (NOT passed). Gate order: lint-format-jsts(oxlint1.69+biome2.5) -> lint-format-py(ruff0.15.17) -> tsc -> basedpyright -> tests-coverage python -> tests-coverage jsts -> sast(opengrep) -> gitleaks8.30.1 -> osv -> charter.

## DONE (pushed b7fb982c)
- basedpyright standard (pyrightconfig.json, include backend/app) driven 209 errors -> 0. NOW GREEN IN CI.
- gitleaks: 0 over history (allowlist docs/reports/scanner-baselines/ generated dumps + $SONAR_TOKEN curl + sk_test_placeholder + fake test PEM).
- pytest.ini `pythonpath = backend` so root `pytest --cov` imports app (gate runs from root, no PYTHONPATH).
- fixed 2 stale audit-script tests (AdrianaArt->momentstudio rename; severe-issues filename).

## KEY GOTCHA: CI runs gate-2 basedpyright WITHOUT backend deps
- Local deps-installed run masks errors CI sees. MUST also run a no-deps venv. BUT even that is imperfect: Python version matters (CI 3.12 vs my 3.14 typeshed differ).
- `isinstance(exc, HTTPException)` then `exc.detail` FAILS in CI no-deps (HTTPException -> Unknown, narrows to Exception). Fix = `getattr(exc, "detail", exc)`. Only caught by CI, not by my local no-deps 3.14 run.
- stripe objects: `dict(stripe_obj)` works WITH deps, FAILS no-deps (stub not mapping). Use `cast(dict[str,Any], ...)` — stable both ways. `stripe = cast(Any, stripe)` at module top does NOT fully neutralize in no-deps.

## REMAINING BLOCKER: gate-tests-coverage python = 62.10% vs 100% required
- `pytest --cov --cov-branch --cov-fail-under=100` from root, NO --cov scope, NO .coveragerc -> measures ENTIRE repo (40548 stmts, 12379 missing). 333 tests pass.
- Repo's own backend.yml never enforced coverage; lean 100% is brand new. Infeasible in one pass (whole-app + scripts/ at 45-99%). NOT fixable without writing hundreds-thousands of tests.
- jsts coverage gate ALSO will fail next (frontend has only `ng test` Karma, no test:coverage / vitest|jest --coverage script; 65 e2e specs). Not reached yet (python coverage aborts first).

## Type-fix patterns used (all REAL, no blanket ignores)
model_validate ORM->Read schema returns; TypedDict for dict-unpack-into-pydantic; AdminPaginationMeta/PaginationMeta constructors; Decimal passed directly (drop float()); isinstance(engine, AsyncEngine) narrowing; import anyio.to_thread (avoid __getattr__ BrokenWorkerInterpreter shim); rename shadowing status/`_` params; Subquery/ColumnElement[bool]/Flowable typing; Body(...) not Ellipsis default.

Clone: C:\Temp\momentstudio-lqg-<ts> (Windows). venvs: .venv-lqg (deps), .venv-ci (no deps).
