---
name: autoresearch
description: Use when the user wants to push a measurable metric PAST its current baseline through many small autonomous variants — make coverage higher, raise a pass rate, improve a benchmark score, tune a config, or iterate until a number hits a target. Each variant is committed BEFORE measuring and auto-reverted if any tracked axis regresses, so the working tree only ever keeps wins. Skip for a one-shot bug with a known fix, or when the user wants a direct implementation without exploration.
license: Skill MIT (this file). Optimization-loop concept adapted from ResearcherSkill by Krzysztof Dudek (MIT) — github.com/krzysztofdudek/ResearcherSkill. No upstream code is vendored; only the keep/discard-with-git-revert pattern is reused.
allowed-tools:
- Read
- Bash
- Edit
- Write
metadata:
  version: 0.1.0
  compatibility: claude-code codex cursor gemini-cli opencode
  source: https://github.com/krzysztofdudek/ResearcherSkill
  upstream_author: Krzysztof Dudek
---

# Autoresearch — metric-maximizing optimization loop

Drive a measurable metric **above its baseline** by running many small variants autonomously. The loop's guarantee: every variant is committed BEFORE it is measured, and any variant that regresses is reverted via git, so the working tree only ever accumulates wins. The discarded variant survives in the reflog (recoverable as a SHA) but leaves the branch clean.

## How this differs from the verification skills

This MAXIMIZES a metric past a moving baseline through repeated keep-or-revert trials. It is not `verification-loop` / `tdd-workflow` (which drive a fixed pass/fail gate to GREEN once) and not `fresh-context-verify` (which re-derives one load-bearing value in a clean context). Use this only when "better than before" is a measured number you want to keep pushing.

## Non-negotiables

1. **Commit before you measure.** No measurement runs against an uncommitted variant — otherwise a revert cannot cleanly undo it.
2. **Log before you revert.** Record the variant's SHA and every axis value to a tracking file FIRST; a reverted SHA is reflog-only, so the log is the audit trail.
3. **Revert on any regression.** If ANY tracked axis drops below baseline, `git reset --hard HEAD~1`. No partial keeps.
4. **Stay in declared scope.** Only modify files the user put in scope. Never `--no-verify`; never force-push.

## Phase 0 — Resume check

If a tracking file (`.autoresearch/log.tsv`) already exists, read it, report the current best-vs-baseline and last status, and ask the user to **resume** (continue from the best SHA) or **start fresh** (archive the old log, re-baseline). Otherwise go to Phase 1.

### Phase 1 — Scope the run (ask before iterating)
### Phase 2 — Baseline (variant #0)
### Phase 3 — The keep/discard loop
### Guardrails (mandatory)
### Coverage recipe (4-axis gate against `.coverage-thresholds.json`)
### Phase 4 — Wrap-up
