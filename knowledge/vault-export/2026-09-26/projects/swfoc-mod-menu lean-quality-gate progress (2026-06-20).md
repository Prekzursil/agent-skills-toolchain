---
title: swfoc-mod-menu lean-quality-gate progress (2026-06-20)
type: note
permalink: main/projects/swfoc-mod-menu-lean-quality-gate-progress-2026-06-20
tags:
- swfoc
- lean-quality-gate
- ci
- basedpyright
- coverage
---

# swfoc-mod-menu lean-quality-gate progress

Branch: feat/lean-quality-gate. Lean gate = reusable workflow `Prekzursil/quality-zero-platform/.github/workflows/reusable-quality.yml@v1`.

## FIXED (commit bb802cb) — gate-types basedpyright now GREEN
- Root cause: scripts/quality/check_{codacy,deepscan,sentry,sonar}_zero.py do `sys.path.insert(scripts/)` then `from security_helpers import ...`. basedpyright (static) can't follow runtime path mutation → 4 reportMissingImports errors. Prior fix 57beadc fixed attribute/ghidra issues but missed these 4.
- Fix: added in-repo `pyrightconfig.json` `{ "typeCheckingMode": "standard", "extraPaths": ["scripts"] }`. extraPaths mirrors the runtime sys.path (REAL import resolution, not a blanket ignore); typeCheckingMode=standard keeps the proven bar (gate's strict default would flood ~39 reportAny/Unknown). Gate honors a caller pyright config when present → runs bare `basedpyright` → 0 errors/0 warnings/0 notes locally. CONFIRMED green in CI run 27856531595.
- Local repro note: basedpyright 1.39.8 has NO `--typecheckingmode` CLI flag (set via config only); CI's flag works because gate passes it only when no caller config — once config present it runs bare.

## REMAINING BLOCKER — gate-tests-coverage python (now surfaces, exit 1)
- After basedpyright went green, the next gate ran for the first time and fails.
- Root cause = TEMPLATE DETECTOR BUG: detector `py_tests` glob includes bare `tests/**` and `**/tests/**` (extension-agnostic). This repo's C# tests live under `tests/SwfocTrainer.Tests/**/*.cs` → glob matches → `pytests=true` even though there are ZERO `.py` test files. With no Python coverage config, gate hits FAIL branch ("Python source + tests present but no coverage config").
- Reality: all 18 Python files are standalone CLI/CI utility scripts + Ghidra-runtime-only helpers (tools/ghidra/* import `ghidra.*`). Repo's OWN main ci.yml line 164 declares `sonar.coverage.exclusions=tests/**,scripts/**,tools/**,native/**` — Python tooling is INTENTIONALLY coverage-excluded. `.coverage-thresholds.json` command is dotnet-only.
- No vacuous in-repo pass: `coverage report --fail-under=100` with no data = exit 1 ("No data to report"), so a no-test + coveragerc trick does NOT pass.

## Correct fixes (need a decision — NOT done)
1. Template fix (architecturally correct, out-of-repo): change `tests/**`/`**/tests/**` → `tests/**/*.py`/`**/tests/**/*.py` in quality-zero-platform reusable-quality.yml @v1 detector, so C# test dirs don't false-trigger the Python coverage lane.
2. OR dedicated Python TDD: real 100% unittest coverage for ~12 testable scripts (5 hit live HTTP APIs → need mocking; argparse CLIs) + `.coveragerc` omitting tools/ghidra/* runtime-only. CONTRADICTS the repo's own scripts/**/tools/** coverage-exclusion policy — busywork on code the project deliberately excludes.

Recommendation: option 1 (template glob fix). The basedpyright work is real and merged-ready; coverage gate is a template false-positive needing the orchestrator/user to pick path.
