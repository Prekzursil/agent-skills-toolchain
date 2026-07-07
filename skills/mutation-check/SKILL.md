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
python mutation_check.py src/calc.py -- python -m pytest tests/test_calc.py -q

# Scope to one function (repeat --function for more); cap the run cost
python mutation_check.py src/calc.py --function is_adult --max-mutations 10 \
    -- python -m pytest tests/test_calc.py::test_is_adult -q

# Just enumerate the mutation sites (no test run)
python mutation_check.py src/calc.py --list

# Run the tests from a specific directory (so imports resolve)
python mutation_check.py src/calc.py --cwd src -- python -m pytest -q
```

Options: `--function/-f NAME` (repeatable), `--max-mutations N` (0 = unlimited,
default 20), `--timeout SEC` (per test run, default 300), `--cwd DIR`, `--list`.

## Mutation set (small on purpose)

| kind | change |
|------|--------|
| boolean-flip | `True` ↔ `False` |
| comparison-swap | `==`→`!=`, `<`→`>=`, `<=`→`>`, `>`→`<=`, `>=`→`<` (negation/boundary) |
| arithmetic-swap | `+`↔`-`, `*`↔`/` |
| return-value | `return X` → `return None` |
| boundary | numeric literal `n` → `n + 1` (off-by-one probe) |

## Exit codes (so it can gate)

- `0` — every mutation KILLED; tests assert behaviour at every mutated site.
- `1` — at least one mutation SURVIVED; a Goodhart-green gap to fix.
- `2` — operational error, could not assess (unparseable source, no mutable sites,
  **red baseline**, or the plain AST round-trip changed behaviour). Fail-safe: it
  never reports a false green when it couldn't actually run the check.

## Safety

The real source file is mutated in place (so the tests import the mutated module),
but the original bytes are captured up front, a temp backup is written, the file is
restored after **every** run and again in a `finally`, and byte-identity is verified
at the end (repaired from the backup if it ever drifts). The file is left exactly as
found even on exception or Ctrl-C. Stdlib only; requires Python 3.9+ (`ast.unparse`).

## Common mistakes

- **Reading a survivor as a source bug.** A survivor means the *test* is weak at
  that site — strengthen the assertion, don't "fix" the code.
- **Red baseline.** If the suite is already failing, exit 2 fires; fix the tests
  first — mutation results are meaningless against a red baseline.
- **PATH resolution.** Use `python -m pytest`, not a bare `pytest`, and pass
  forward-slash paths so the command runs the same on Windows and POSIX.
- **Import scope.** If tests can't import the module under test, set `--cwd` to the
  directory pytest should run from.
