---
name: autoresearch
description: Use when the user wants to push a measurable metric PAST its baseline through many small autonomous variants - raise coverage, a pass rate, or a benchmark score, tune a config, or iterate until a number hits a target. Each variant is committed BEFORE measuring and auto-reverted if any tracked axis regresses, so the tree only keeps wins. Skip for a one-shot bug with a known fix.
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

## Phase 1 — Scope the run (ask before iterating)

Confirm with the user, compactly, before any variant:

1. **Metric** — what number are we maximizing, and the exact command that prints it.
2. **Baseline source** — the threshold/target each axis must beat. For coverage work this is `.coverage-thresholds.json` (the repo's single source of truth — read it, do not hardcode numbers).
3. **Scope** — which files may change; what is off-limits.
4. **Run command** — the single command (or chain) that builds + measures one variant. The whole chain must succeed or the variant is a CRASH.
5. **Termination** — target value, max variants, or "run until interrupted" (default: until the user stops it or the target is hit).

Repeat the config back in a compact table and get explicit confirmation. Then work autonomously.

## Phase 2 — Baseline (variant #0)

With NO change, run the metric and record variant #0. This is the bar every later variant must clear. For a coverage run, baseline = the four axis values from `.coverage-thresholds.json` (see the coverage recipe below).

## Phase 3 — The keep/discard loop

For each variant N (THINK -> COMMIT -> MEASURE -> COMPARE -> DECIDE):

1. **THINK** — pick one hypothesis (one variable changed) and write it to the log.
2. **COMMIT FIRST** — make the change in scope, then:
   ```
   git add -A && git commit -m "autoresearch #N: <hypothesis>"
   ```
   (Use a real one-line hypothesis in place of the placeholder.) The commit must exist before any measurement.
3. **MEASURE** — run the metric command. If the build/measure chain fails: CRASH (go to step 6).
4. **COMPARE** — read each axis value and compare against the baseline/threshold for that axis. Improvement must clear a small noise margin (e.g. ~0.1%); equal-but-simpler counts as a keep.
5. **DECIDE**
   - **KEEP** — every tracked axis is >= baseline AND at least one improved (or it's equal with simpler code). Leave the commit; this variant becomes the new baseline.
   - **DISCARD** — ANY axis regressed below baseline. Log the SHA + values first, then `git reset --hard HEAD~1`. The branch returns to the prior keep; the discarded SHA stays reflog-recoverable.
6. **CRASH** — `git reset --hard HEAD~1`, log status=crash. Trivial cause (typo, missing import): fix and re-run ONCE. Fundamental (OOM, missing dep): log and move on. 3 crashes in a row: rethink the approach.
7. **LOG** — append a row to `.autoresearch/log.tsv`: `variant  sha  status  <axis values...>  hypothesis`. This row is written BEFORE any reset in steps 5/6.

### Guardrails (mandatory)

- **3 discards in a row** — stop and write a short review of whether to continue or change tactics before the next variant.
- **Best unchanged for ~8 variants** — you are on a plateau; invert a core assumption (e.g. if "more X helped", try minimal X) instead of tweaking the same variable.
- **Anchor drift** — if a measured value has been load-bearing for a long chain and the loop keeps not converging, invoke the existing **`fresh-context-verify`** skill to re-derive it in a clean context. Do NOT reimplement that check here.

## Coverage recipe (4-axis gate against `.coverage-thresholds.json`)

When the metric is test coverage, the four axes are `lines`, `branches`, `functions`, `statements`, and the per-axis bar is read from `.coverage-thresholds.json` (`thresholds.{lines,branches,functions,statements}`).

1. Read the four threshold numbers from `.coverage-thresholds.json`. These are the baseline; never hardcode them.
2. For each variant, after the commit, measure with the JSON reporter:
   ```
   npx jest --coverage --json --outputFile=.autoresearch/cov.json
   ```
   Read the four percentages from `total.lines.pct`, `total.branches.pct`, `total.functions.pct`, `total.statements.pct` in that file. (If the repo's enforcement command in `.coverage-thresholds.json` differs, prefer it — it is the source of truth.)
3. **4-axis compare:** for axis in {lines, branches, functions, statements}, require `total.<axis>.pct >= thresholds.<axis>`. If ANY axis is below its threshold, the variant REGRESSED.
4. **Revert on any regression:** `git reset --hard HEAD~1` (after logging the row). The discarded SHA is reflog-only — recover it later with `git reflog` if a discarded idea is worth revisiting.
5. KEEP only when all four axes meet or beat their thresholds and the variant advanced the goal (e.g. closed a coverage gap, or held coverage while simplifying).

Add `.autoresearch/` to `.gitignore` so the tracking file and `cov.json` never get committed into a variant.

## Phase 4 — Wrap-up

On termination: re-run the metric from the global best to confirm the final number, check out the SHA holding that best, and report a compact summary — baseline vs best per axis, kept vs discarded counts, and the top variants that moved the metric.
