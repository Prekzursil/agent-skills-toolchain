---
title: 'Reframe quality gate: build agents must run FORMATTERS not just linters'
type: note
permalink: main/projects/reframe/reframe-quality-gate-build-agents-must-run-formatters-not-just-linters
tags:
- reframe
- ci
- quality-gate
- gotcha
- formatter
- workflow
---

# Reframe `gate-lint-format` keeps redding — agents skip the FORMATTERS

**Symptom:** Reframe's `quality` CI step `gate-lint-format (pre-commit run --all-files)` failed 3× this session on Provider-Hub PRs (#212, #213×2) even though each WU agent reported "ruff check clean / vitest 100%."

**Root cause:** parallel build agents run the LINTERS (`ruff check`, `oxlint`, `vitest`) but NOT the FORMATTERS that the pre-commit gate enforces:
- `ruff format` (sidecar Python) — agents ran `ruff check` only; new modules/tests were unformatted.
- `@biomejs/biome@2.5.0 format` (renderer TS/TSX/CSS) — new components unformatted.
- `oxlint --config app/.oxlintrc.json --deny-warnings` (note: CI uses `--deny-warnings`; `--fix` alone misses unfixable warnings).

**FIX (fold into every code-writing agent's RAILS + run before any Hub/Reframe push):**
```
ruff check sidecar && ruff format sidecar
( cd app && npx @biomejs/biome@2.5.0 format --write . && npx oxlint --config .oxlintrc.json --fix --deny-warnings )
# then verify all are idempotent/clean:
ruff format --check sidecar ; npx @biomejs/biome@2.5.0 format . ; ( cd app && npx oxlint --config .oxlintrc.json --deny-warnings )
```
Then stage EXPLICIT paths only (git on this repo stores LF; the flood of "LF will be replaced by CRLF" warnings is cosmetic — `git diff --name-only` shows the real, small changed set).

**Pins (match CI `.pre-commit-config.yaml` / quality.yml):** ruff 0.15.17 · biome 2.5.0 · oxlint 1.70.0 (mirror 1.69.0) · basedpyright 1.39.8. Sidecar gate = `pytest --cov=media_studio --cov-branch --cov-fail-under=100` (WSL `/tmp/msv` py3.12). Renderer = `npx vitest run --coverage` (vitest thresholds:100, NOT jest). No `.coverage-thresholds.json` in this repo.

Relates to [[reframe-ai-program-grill-complete-preview-fixed-plan-gating-2026-06-17]].