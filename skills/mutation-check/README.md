# mutation-check — empirical test-strength gate (agentic-perfection gem C3)

A cheap, execution-grounded check of test **strength**, not just coverage. Coverage
and a green `pytest` only prove the tests *execute* the code; this proves they
*assert its behaviour*. See
[`docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md`](../../docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md).

A **tool run on demand** (not a Stop hook). Given a changed source file and the
command that runs its tests, it applies a small, high-signal mutation set to the
function(s) under test and, for each, re-runs the tests asking: *did at least one
test go RED?* A mutation the suite leaves green (**survived**) is a Goodhart-green
gap — a behaviour the tests never actually check.

## Why

bFinder measured **17.5%** of expected behaviours untested even at >90% line+mutation
coverage. The done-signal the agent controls (coverage / "tests pass") is a proxy it
can satisfy in a vacuum. This anchors to an **external** signal it can't fake: does a
real test process exit non-zero when the code is provably broken?

## Install

Copy the folder next to the other on-demand tools and expose the skill:

```
tools/mutation-check/            (or wherever on-demand tools live)
  mutation_check.py              — the CLI (stdlib only; Python 3.9+)
  test_mutation_check.py         — 29 tests (pure core + stubbed run_check + real e2e)
  SKILL.md                       — the /mutation-check wrapper
  README.md                      — this file
```

Register `SKILL.md` where the harness discovers skills (e.g.
`~/.agents/skills/mutation-check/SKILL.md` per the canonical skills path), or invoke
the CLI directly. No dependencies to install.

## Quick start

```bash
# Fail (exit 1) if any mutation to calc.py survives its tests
python mutation_check.py src/calc.py -- python -m pytest tests/test_calc.py -q

# Scope to one function; just list sites; run tests from a directory
python mutation_check.py src/calc.py --function is_adult -- python -m pytest -q
python mutation_check.py src/calc.py --list
python mutation_check.py src/calc.py --cwd src -- python -m pytest -q
```

Everything after `--` is the test command, run verbatim (no shell). Prefer
`python -m pytest`.

## What "strong vs weak tests" looks like

Same source, two suites — the tool reports the difference:

```
# WEAK suite (never probes the 17/18 boundary)          -> exit 1
KILLED   #0 return-value    L2 `return age >= 18` -> `return None`
KILLED   #1 comparison-swap L2 `age >= 18` -> `age < 18`
SURVIVED #2 boundary        L2 `18` -> `19`
SUMMARY: 3 mutation(s), 2 killed, 1 survived
FAILED: mutation-check 1 surviving mutation(s) — a Goodhart-green gap …: boundary L2 `18` -> `19`

# STRONG suite (asserts is_adult(18) is True)           -> exit 0
KILLED   #0 return-value    L2 `return age >= 18` -> `return None`
KILLED   #1 comparison-swap L2 `age >= 18` -> `age < 18`
KILLED   #2 boundary        L2 `18` -> `19`
SUMMARY: 3 mutation(s), 3 killed, 0 survived
SUCCESS: mutation-check 3/3 mutations killed — tests assert behaviour at every mutated site.
```

## Exit codes

| code | meaning |
|------|---------|
| 0 | every mutation KILLED — tests assert behaviour at every mutated site |
| 1 | ≥1 mutation SURVIVED — a Goodhart-green gap to fix |
| 2 | operational error (unparseable source, no mutable sites, red baseline, or the AST round-trip itself changed behaviour) — never a false green |

## Mutation set

`boolean-flip` (`True`↔`False`) · `comparison-swap` (`==`→`!=`, `<`→`>=`, `<=`→`>`,
`>`→`<=`, `>=`→`<`) · `arithmetic-swap` (`+`↔`-`, `*`↔`/`) · `return-value`
(`return X`→`return None`) · `boundary` (`n`→`n+1`).

## Safety

The source is mutated in place (so the tests import the mutated module) but restored
after every run and again in a `finally`; byte-identity is verified at the end and
repaired from a temp backup if it ever drifts — the file is left exactly as found
even on exception or Ctrl-C. Two pre-flight baselines run first: the real file must
be green, and the plain AST round-trip must be green (else unparse changed behaviour
and results would be unreliable). `PYTHONDONTWRITEBYTECODE` is forced on so a mutated
write can never be shadowed by a stale `.pyc`.

## Development

```bash
python -m pytest test_mutation_check.py -q   # 29 passing
python -m ruff check .                        # clean
```
