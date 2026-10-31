---
name: mutation-check
description: Use at the verify boundary to empirically test test-STRENGTH (not just coverage) — given a changed Python source file and the command that runs its tests, it applies a small high-signal mutation set to the function(s) under test and asserts each mutation makes at least one test go RED. A mutation the suite leaves green ("survived") is a Goodhart-green gap where the tests execute the code but don't assert its behaviour. Use it as a gate (exit 1 on any survivor) after coverage is already green; do NOT use it to find bugs in the source (it probes the TESTS) or on non-Python code.
---

# mutation-check — the execution-grounded test-strength gate

## Overview

Coverage and a green `pytest` prove the tests *execute* the code; they say nothing
about whether the tests *assert its behaviour*. bFinder found **17.5%** of expected
behaviours untested even at >90% line+mutation coverage — the classic Goodhart-green
gap (see `docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md`, gem C3).

This is a **tool run on demand**, not a Stop hook. It mutates the function under
test, re-runs the affected tests, and reports which mutations **survived** (all
tests still green ⇒ that behaviour is unasserted). It anchors to an external signal
the implementer can't fake: *does a real test process exit non-zero when the code is
provably broken?*

## When to reach for it

- At the verify/commit boundary of a change, after coverage is already green, to
  confirm the new tests actually *catch* regressions — not just touch the lines.
- When a suite looks suspiciously green ("100% coverage, all pass") and you want a
  cheap, empirical strength check before trusting it.

Do **not** use it to find bugs in the source (it grades the *tests*), on non-Python
files, or as an always-on hook (it spawns one test run per mutation).

## Usage

```
python mutation_check.py [options] SOURCE -- TEST COMMAND...
```

Everything after `--` is the test command, run verbatim (no shell). Prefer
`python -m pytest` so it resolves without relying on PATH/PATHEXT.

```bash
# Gate a change: mutate the whole file, run its tests, fail if any mutation survives

### Scope to one function (repeat --function for more); cap the run cost
### Just enumerate the mutation sites (no test run)
### Run the tests from a specific directory (so imports resolve)
### Mutation set (small on purpose)
### Exit codes (so it can gate)
### Safety
### Common mistakes
