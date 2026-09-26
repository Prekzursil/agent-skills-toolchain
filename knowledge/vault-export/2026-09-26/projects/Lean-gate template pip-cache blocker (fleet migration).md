---
title: Lean-gate template pip-cache blocker (fleet migration)
type: report
permalink: main/projects/lean-gate-template-pip-cache-blocker-fleet-migration
tags:
- lean-quality-gate
- quality-zero-platform
- fleet-migration
- ci-blocker
---

# Lean-gate template pip-cache blocker (fleet migration)

2026-06-17, during Step-3 migration of `Prekzursil/devextreme-filter-go-language` to the lean 6-gate (additive PR #34).

## Blocker (TEMPLATE bug, not caller PR)
The shared reusable workflow `Prekzursil/quality-zero-platform/.github/workflows/reusable-quality.yml@feat/lean-quality-template` fails at **Set up Python** for any repo that has stray `*.py` files but NO pip lockfile.

Error:
```
##[error]No file ... matched to [**/requirements.txt or **/pyproject.toml]
```
Cause: language-detect sets `python=true` on ANY `*.py` (e.g. CI helper scripts `scripts/security_helpers.py`, `scripts/quality/gocover_to_sonar_generic.py`), then `actions/setup-python` runs with `cache: pip`, which hard-fails when there is no `requirements.txt`/`pyproject.toml`. Whole job fails before any gate runs (5s fast-fail).

## Fix (template-side, owned by quality-zero-platform)
In `feat/lean-quality-template`, make pip cache conditional:
- drop `cache: pip`, OR
- `cache: ${{ hashFiles('**/requirements.txt','**/pyproject.toml') != '' && 'pip' || '' }}`, OR
- only set up Python for a real Python project, not stray helper scripts.

## Fleet impact
Any Go/mixed repo carrying `.py` helper scripts without a pip lockfile will hit this. Likely affects several of the 13 fleet repos. Fix the template ONCE; the additive callers are correct.

## devextreme-filter-go-language specifics
- Go module `transaction-filter-backend`, go 1.25.4. SECURITY.md already existed (good format).
- Dependabot already configured (gomod + github-actions).
- Coverage genuinely 100% on Linux CI; the only Windows-local sub-100% funcs (`ListSchemaDefinitionsHandler`, `LoadSchemaDefinitionHandler`, `listDynamicTablesHandler`, `ListDynamicTables`) are covered by tests that `t.Skip()` on Windows (Unix-only error semantics), documented in-source: "gate runs on Linux CI". So coverage-gate kept at 100%, no tests faked, no gate lowered.
- coverage-gate.sh mirrors the PROVEN per-package recipe in the repo's existing `sonar.yml` (per-package profiles concatenated; `-coverpkg` deliberately avoided — it leaves other packages' statements at 0 in the merged profile and produces false sub-100%).
- Archive cut: branch+tag `archive/pre-lean-gate` at HEAD ee360be.
- PR #34 left as DRAFT pending the template fix.

## Tooling gotcha (Windows harness)
Write/Edit/Read tools resolved `/tmp/...` to `C:\tmp\...` while the Bash tool's `/tmp` = `C:\Users\Prekzursil\AppData\Local\Temp`. Files written by Write landed in the wrong dir; had to `cp` from `/c/tmp/...` into the real clone, and write scripts via Bash heredoc instead. Use the real Windows path (`C:/Users/Prekzursil/AppData/Local/Temp/...`) for Read/Edit on /tmp clones.
