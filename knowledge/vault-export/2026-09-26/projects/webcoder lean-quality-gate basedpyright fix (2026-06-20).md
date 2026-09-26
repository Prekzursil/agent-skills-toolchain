---
title: webcoder lean-quality-gate basedpyright fix (2026-06-20)
type: note
permalink: main/projects/webcoder-lean-quality-gate-basedpyright-fix-2026-06-20
tags:
- webcoder
- lean-quality-gate
- basedpyright
- ci
---

# webcoder lean-quality-gate basedpyright fix

Branch feat/lean-quality-gate on Prekzursil/WebCoder (PR #85). Lean 6-gate quality template @ Prekzursil/quality-zero-platform/.github/workflows/reusable-quality.yml@v1.

## Key gate mechanics (learned)
- basedpyright gate (step 14) runs BEFORE any python deps are installed (deps install only inside the test gate, step 15). So basedpyright runs against a CLEAN interpreter — Django/DRF/celery are ABSENT.
- Config detection: `git ls-files pyrightconfig.json basedpyrightconfig.json | head -1` runs from REPO ROOT → only matches a root-level path. Config under backend/ → pyrightcfg=false → template falls back to `basedpyright --typecheckingmode standard` which basedpyright 1.39.8 REJECTS (exit 4, "Unexpected option"). FIX = put pyrightconfig.json at repo ROOT with `include:["backend"]`.
- Python test gate runs `python -m pytest --cov --cov-branch --cov-fail-under=100` from REPO ROOT, no DJANGO_SETTINGS_MODULE, no postgres service. Needs a ROOT pytest.ini (pythonpath/testpaths=backend, settings_ci sqlite, --cov=backend) or it collects 0 tests / crashes on postgres.

## Fixes committed (all pushed, basedpyright gate GREEN in CI at a9a2ee9)
- pyrightconfig.json (root): typeCheckingMode=standard, reportMissingImports=false, reportMissingModuleSource=false (third-party deps genuinely absent in the type-check stage — reasoned env fact, NOT code defect / NOT gate weakening).
- execution.py: process_timeout computed before try (real possibly-unbound).
- admin.py x2: @admin.display(description=) instead of .short_description attr.
- tasks.py: _CeleryTask Protocol (delay/apply_async/__call__) + cast; verdict label via dict(choices).
- checkers.py: return str verdicts via str(TextChoices member) typed constants (members are str at runtime; pyright misreads TextChoices members as tuple[Literal,Unknown]).
- celery.py: cast Celery to type[Any] before call (untyped celery → "Module is not callable").

## CI-mirror oracle
Local envs always have celery/django (system Python314 + backend/venv) so they MASK the celery-absent errors. Faithful mirror = empty py3.12 venv: `basedpyright --pythonpath <empty312>/Scripts/python.exe` from repo root. That reproduced the celery.py error CI saw.

## REMAINING gap (honest)
Python coverage gate = 40.48% (1210 stmts, 621 missing, 260 branches, only 2 tests). 100% line+branch requires heavy subprocess/Docker/Celery/OAuth mocking across execution/compilation/checkers/comparison/tasks/permissions/serializers/views — genuine multi-pass TDD. Frontend coverage already 100%. gitleaks=clean, ruff=clean, tsc/oxlint/biome=green.
