---
title: 'Verified-green honesty: read the test SUMMARY line, not exit-code + coverage%;
  async claims need caveats'
type: note
permalink: main/feedback/verified-green-honesty-read-the-test-summary-line-not-exit-code-coverage-async-claims-need-caveats
tags:
- feedback
- honesty
- verification
- anti-sycophancy
- ci
- coverage
- self-correction
---

# Verified-green honesty — don't infer "tests passed" from exit-code + coverage%

**USER-adjacent behavior correction (self-caught + Stop-hook-caught, 2026-07-17/18, QZT heal).**

## What went wrong
I claimed "verified green locally" for a QZT fix after running `python -m coverage run -m unittest discover` (a background task that reported "exit code 0") + `coverage report --fail-under=100` (100.00%). I did NOT read the actual unittest `Ran N tests ... OK` / `FAILED (failures=N)` line. CI then failed with **2 more test failures** I'd missed.

**Why:** (a) `coverage report` computes % from the `.coverage` data file **regardless of whether tests passed or failed** — 100% coverage ≠ tests green. (b) I trusted a background task's "exit 0" without seeing the summary; the tail I captured showed a test's JSON stdout, not the unittest summary (which goes to stderr).

## The rule (how to apply)
- For any "tests pass / green" completion claim, grep the EXPLICIT terminal summary: `grep -iE 'Ran [0-9]+ tests|^OK$|FAILED \('` AND confirm the explicit process exit code — never infer pass from coverage% or a background "exit 0" alone.
- Run the FULL gate the CI runs (e.g. `bash scripts/verify`), not just the subset (I skipped the node + validate steps and CI caught a step-4 failure the unittest-only run couldn't).
- **Async forward claims need a caveat:** "the 5 alerts will close" / "fully clean" — a code-scanning alert closes only when the post-merge CodeQL scan finishes + uploads. State "fix merged + scan in-progress; alerts still open now" — don't call it "clean" until `code-scanning/alerts?state=open` = 0. The Stop-hook "completion language without verification" flag caught this twice and was right both times.

**Why this matters:** reinforces AGENTS.md §7 (fresh-context generator-critic before a conclusion) at the mechanical level — the cheapest external check (read the summary line) beats a confident-but-wrong "green." Links [[fleet-0-dependabot-alerts-always-grill-decision-log-2026-07-17]].