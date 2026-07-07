# journey-coverage — every declared user-journey must be RUN before "done"

The third functional-acceptance gem, after `claim-guard` (G1) and `test-tamper-guard`
(G2). See [`docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md`](../../docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md).

## What it does
A **Stop** hook. Where `claim-guard` asks *"does this 'it works' claim have ANY e2e
evidence?"*, this asks the **completeness** question: when the final message claims the
app is **done / ready / shippable**, was **every** declared user-journey / E2E spec in
the repo actually **run this turn**? A journey that exists on disk but was never
executed is the classic green-but-broken blind spot — the golden-journey nobody ran.

## The two external signals (neither authored in-context)
1. **Journey spec files on disk** — globbed (`*golden-journey*.spec.*`, `**/e2e/**/*.spec.*`,
   `cypress/e2e/**/*.cy.*`, `**/tests/e2e/**/*.py`, …), skipping `node_modules`/`dist`/…
2. **The `claim-guard` Bash-exit ledger** — the `ok=true` commands run this turn
   (`%TEMP%\claude-claim-ledger\<session>.ndjson`; override `CLAIM_GUARD_LEDGER_ROOT`).

A journey is **covered** iff an `ok=true` command this turn **named** it (full path /
basename / stem) **or** was a **bare broad e2e runner** (`playwright test`, `cypress run`,
`npm run e2e`, `pytest -m e2e`, …) that runs all specs. A *targeted* `playwright test
<spec>` covers only that spec — it never masks the other journeys. A plain `pytest` /
`jest` (unit run) does **not** count.

## Behavior
- Fires only on an assertive, **non-hedged** app-is-done claim (same hedge suppression as
  claim-guard). Silent otherwise, or when the repo has no journey specs, or when every
  journey was covered.
- `JOURNEY_COVERAGE_MODE`: `warn` (default — inject `additionalContext` listing the
  un-run journeys, exit 0) · `off` · `block` (exit 2 **only** for a done-claim with
  uncovered journeys).
- **Fail-open**: any exception → silent exit 0. Non-nagging. Stdlib only.

## Registration (settings.json)
Add a `Stop` entry alongside the existing ones (event-ledger, claim-guard):
```json
{ "type": "command",
  "command": "python C:/Users/Prekzursil/.claude/hooks/journey-coverage/check.py",
  "timeout": 10,
  "statusMessage": "Journey-coverage: checking declared journeys were run" }
```
Depends on `claim-guard/ledger-write.py` (PostToolUse) populating the shared ledger.

## Files
```
hooks/journey-coverage/
  check.py                     — the hook (pure core: uncovered_journeys / find_journey_specs)
  test_journey_coverage.py     — 19 tests (pure core + warn/block/off + fail-open)
  README.md                    — this document
```
