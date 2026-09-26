---
name: Quality Rollup v2 resume context
description: In-flight refactor of quality-zero-platform rollup + gates. Brainstorm
  done, design committed, awaiting design-review-gate in a fresh session inside the
  correct project cwd.
type: project
permalink: main/claude-memory/documents-git-hub-quality-zero-platform/qrv2-resume
---

## Status

**Phase:** Phase 3 (brainstorming) complete. Design doc committed. Phase 4 (gates + plans) pending.

**Branch:** `feat/quality-rollup-v2` (off `main` at commit `b2fc326`)
**Design commit:** `93ae3f6` — `docs(plans): add quality-rollup-v2 design`
**Design file:** `docs/plans/2026-04-09-quality-rollup-v2-design.md`

## Next actions (in order)

1. **Run the 5-agent Design Review Gate** on the design doc. Invoke via `/review-design` or the `design-review-gate` skill. All 5 agents (PM, Architect, Designer, Security, CTO) must approve before proceeding to `writing-plans`. This is MANDATORY per the repo's CLAUDE.md — this repo is NOT external work and its own governance rules apply.
2. After all 5 approve → run `superpowers:writing-plans` for **PR 1 only** (the "Rollup rewrite + patch generators" PR). The design already lists the 3-PR scope slicing — don't try to plan all 3 at once.
3. After PR 1 plan is written → run **plan-review-gate** (3 adversarial reviewers: Feasibility, Completeness, Scope+Alignment). All must PASS.
4. Then execute PR 1 via orchestrated execution or subagent-driven development (user's choice).
5. Repeat steps 2-4 for PR 2 and PR 3.

## User decisions locked in (from brainstorm Q1-Q8)

| Q | Decision |
|---|---|
| Q1 | **C** — dual output: canonical JSON + rendered markdown |
| Q2 | **D** — multi-view rendered markdown (default: by file; collapsible alt views: by provider, by severity, autofixable) |
| Q3 | **E** — hybrid dedup taxonomy: full canonical categories for security+quality, file+line collapse for style |
| Q4 | **D+E** — deterministic patch generators (~30 mechanical categories) + LLM fallback scaffold (gated off by default) |
| Q5a | **D** — strict 100% line+branch coverage with declared excludes in `[tool.coverage]` |
| Q5b | **C** — reuse existing `run_coverage_gate.py` + `assert_coverage_100.py` in `scripts/verify` |
| Q5c | **A** — fix SonarCloud upload via `sonar-project.properties` + `SonarSource/sonarqube-scan-action` step in `reusable-scanner-matrix.yml` coverage lane |
| Q6 | **B** — minimal `.codacy.yaml` (engines block + excludes) + per-tool config files: `.pylintrc` audit, `.bandit`, `pyproject.toml [tool.ruff]`, `.semgrep.yml` |
| Q7 | **C** — Chromatic + Applitools infrastructure + enable on `momentstudio` (not the other visual repos yet) |
| Q8 | **C** — 3 PRs: (1) rollup rewrite + patch generators, (2) self-governance + SonarCloud + Codacy config, (3) new provider lanes |

## Problems diagnosed (fixed by this work)

1. `build_quality_rollup.py` renders a 3-column table where "Detail" is literally `str(findings[0])` — useless
2. Semgrep, CodeQL, Chromatic, Applitools never in the rollup even when they run
3. `.codacy.yaml` is 5 lines of exclusions only — no engines declared
4. Platform repo has 47 test files but `scripts/verify` doesn't measure coverage (violates "100% by default" policy on the control plane itself)
5. SonarCloud coverage upload is broken — no `sonar-scanner`, no `sonar-project.properties`
6. Codecov gets duplicate uploads from two workflows
7. `build_quality_rollup.py` is NOT invoked by platform's own CI (no dogfooding)

## Architecture summary (full details in design doc §3-9)

- **Canonical finding schema:** `qzp-finding/1` — SARIF-inspired; `file`, `line`, `category`, `severity`, `confidence`, `primary_message`, `corroborators[]`, `fix_hint`, `patch`, `patch_source`, `context_snippet`
- **Taxonomy:** ~40 categories split into security (CWE-keyed), quality (hand-curated), style
- **Dedup:** `(file, line, canonical_category)` for security+quality; `(file, line)` for style
- **Patch tiers:** Tier 1 deterministic (~30 categories, each a Python module with tests); Tier 2 LLM fallback via existing Codex runner, cached by `(file_hash, rule_id, line)`
- **Multi-view rendering:** by-file default + collapsible by-provider / by-severity / autofixable views
- **Self-governance:** `pyproject.toml [tool.coverage]` (strict 100 + excludes) + augment `scripts/verify` to run `coverage run` → `coverage xml` → `assert_coverage_100.py`
- **New lanes:** Semgrep (SARIF), CodeQL (SARIF, reuse Semgrep normalizer), Chromatic (API), Applitools (API)
- **Visual profile schema:** `visual_regression.chromatic.enabled` + `visual_regression.applitools.enabled` per-repo opt-in

## Open items for writing-plans

- Exact rule-ID → canonical category mapping for each provider (1-2h research per provider)
- `ruff` vs `pylint` primacy decision (leaning ruff, pylint as secondary)
- `.bandit` as file vs `pyproject.toml [tool.bandit]` (reliability concern)
- Provider priority list for `pick_primary_by_provider_priority()` (proposal: SonarCloud > Codacy > DeepSource > Semgrep > CodeQL > QLTY > DeepScan)
- Whether PR 1 pre-reserves lane keys for Semgrep/CodeQL/Chromatic/Applitools so PR 3 is purely additive

## How to resume

Open Claude Code inside `C:\Users\Prekzursil\Documents\GitHub\quality-zero-platform\` (cwd = repo root). The project's CLAUDE.md + memory + `.beads/` will load automatically. Then:

```
/start-task resume quality-rollup-v2 design — run the design-review-gate on docs/plans/2026-04-09-quality-rollup-v2-design.md and then proceed to writing-plans for PR 1
```

Or directly:

```
read docs/plans/2026-04-09-quality-rollup-v2-design.md and run /review-design on it
```

## Do not

- Do not re-brainstorm — the design is locked in via Q1-Q8 answers above
- Do not try to plan all 3 PRs at once — plan PR 1 first, execute, then PR 2, then PR 3
- Do not skip the design-review-gate — this repo's CLAUDE.md mandates it (unlike external install work)
- Do not touch `main` directly — all work stays on `feat/quality-rollup-v2` or PR-specific sub-branches