---
name: two-tier-verify
description: Use when repeated code edits are triggering a full test-suite rerun each iteration and burning tokens/time, or before any commit. Splits verification into a cheap INNER loop per edit (only the affected/related tests plus type-check and lint on touched files) and a single OUTER loop at the commit boundary (full suite plus coverage plus held-out E2E/golden-journey plus a scoped mutation check). Gives concrete jest/vitest/playwright and pytest command recipes and the decision rule for which tier to run. NOT a replacement for the golden-journey done-signal (see seed-golden-journey); NOT for one-off single-file scripts where a full run is already trivial.
---

# two-tier-verify

The default agentic edit loop is `edit → rerun the WHOLE suite → read all output → edit again`.
That is the single biggest token/time sink in long repair sessions — ProjDevBench measured
**~4.81M tokens per problem**, dominated by re-running and re-reading tests that the last edit
could not possibly have affected. Test-impact selection (Ekstazi / Microsoft TIA / CloudBees)
cuts test time **32–70%** by running only the tests reachable from the change.

The fix is to **split verification into two tiers** and never confuse them:

- **INNER loop** — runs after *every* edit. Fast, narrow, cheap. Only the tests related to the
  files you touched, plus a type-check and a lint on those files. This is your iteration signal.
- **OUTER loop** — runs *once*, at the commit boundary (and before a PR). Slow, total, external.
  Full suite + coverage threshold + the held-out E2E/golden-journey + a scoped mutation check.
  This is your merge signal.

**Law:** the INNER loop is for *iterating*; it is never a done-signal. Only a green OUTER loop
authorizes a commit. Related-test selection is fast precisely because it is blind to seams it
can't reach — so it can go green while an integration path is broken. That gap is exactly what
the OUTER loop's full suite + golden-journey exist to close.

## The two tiers

| | INNER (per edit) | OUTER (per commit) |
|---|---|---|
| Frequency | every edit / iteration | once, at the commit/PR boundary |
| Target | tests **related to changed files** only | **full** suite |

### Decision rule — which tier, when
### Command recipes — JS / TS (jest, vitest, playwright)
### jest — run only tests that import the changed file(s):
### or, git-driven, all tests related to files changed vs HEAD:
### vitest — run only tests related to the changed files:
### or git-driven since HEAD:
### type-check + lint on what you touched (the "AST" gate):
### Electron/web E2E in the INNER loop: run ONE spec, never the whole E2E suite:
### (or vitest: npx vitest run --coverage)
### enforce the project's threshold — .coverage-thresholds.json is the SSOT if present:
### jest reads coverageThreshold from config; fail the commit if it drops.
### Command recipes — Python (pytest)
