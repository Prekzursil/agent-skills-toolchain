---
name: smallest-check-ladder
description: Use when you need to run "the smallest test that could still catch this change" instead of blindly running the whole suite (or nothing). Provides an invocable L0 to L3 ladder - L0 lint the edited file, L1 impacted tests via deterministic selectors, L2 full suite via longrun, L3 e2e - so a "tests pass" claim is backed by a proportionate check. Never ML "predictive test selection".
origin: gem-hunt-2026-07-12 (A-Tier2, verification-gates #4/#5)
---

# Smallest-Check Ladder (L0 -> L3)

Pick the **smallest rung that could still falsify the change**, run it for real, and
escalate only when the rung passes and you need broader confidence. The point is to make
"I ran the relevant tests" a concrete, reproducible command — not a vibe — while staying
proportionate to the size of the diff.

**Deterministic only.** Every selector on this ladder chooses tests from a *dependency graph*
or a *coverage map* (a fact about the code), never from a learned model that *predicts* which
tests are "probably" relevant. ML predictive test selection is explicitly out of scope: it can
silently drop a test that actually covers the change, which defeats the purpose of the rung.

## The ladder

| Rung | Scope | Cost | Run when |
|------|-------|------|----------|
| **L0** | Lint / typecheck the **edited file(s)** only | ~1s | Every save. Always cheap enough to skip nothing. |
| **L1** | **Impacted** tests — the tests that exercise the changed files | seconds–low tens of s | Default for any code change before claiming "tests pass". |
| **L2** | **Full** suite (+ coverage) | minutes | L1 passed and the change is cross-cutting, or before a PR / task-completion gate. |
| **L3** | **E2E** against the built/packaged artifact | minutes+ | Packaging, wiring, or user-journey surface touched (see packaged-artifact smoke gate). |

Climb from the lowest rung that can catch *this* class of defect. A one-line pure-function
fix rarely needs L3; a change to the Electron main process or the ffmpeg argv builder does.

## Concrete commands

Substitute the actual changed paths for `<files>`.

### L0 — edited-file lint / typecheck
```bash
# Python (Reframe: ruff + basedpyright)
ruff check <files>
basedpyright <files>

# TypeScript (Reframe app/)
npx tsc --noEmit               # project-wide but fast; or eslint just the files:
npx eslint <files>
```

### L1 — impacted tests (deterministic selectors)
```bash
# Python — pytest-testmon: selects tests whose recorded coverage touches the changed code.
#   Deterministic: it replays a stored per-test coverage map, it does not predict.
#   Prerequisite (one-time): pip install pytest-testmon   # the --testmon flag is absent until installed
pytest --testmon                       # uses the .testmondata db built on the prior run
pytest --testmon-noselect <files>      # first run / to (re)seed the db for these files

# JavaScript/TypeScript — dependency-graph selection (deterministic: static import graph)
npx jest --findRelatedTests <files>    # jest projects
npx vitest related <files> --run       # vitest projects (Reframe app/ uses vitest)
```
`--testmon` needs its `.testmondata` db seeded once (run the suite under testmon, or use
`--testmon-noselect`); if the db is stale or missing it falls back to running everything, so
treat a suspiciously-large L1 selection as "seed first, then reselect".

### L2 — full suite (always via longrun; it exceeds 60s)
```bash
# Wrap in longrun per the >60s rule; never a blocking foreground call.
~/source/agent-skills-toolchain/scripts/longrun.ps1 -Id l2-full -HangTimeoutSec 300 \
  -Cmd pytest --cov --cov-report=term-missing
# TS:
~/source/agent-skills-toolchain/scripts/longrun.ps1 -Id l2-vitest -HangTimeoutSec 300 \
  -Cmd npx vitest run --coverage
```
Coverage thresholds are **not** decided here — `.coverage-thresholds.json` remains the single
source of truth and its enforcement command is the blocking gate. L2 just *runs* the suite.

### L3 — e2e against the built artifact
```bash
# Run the project's e2e journeys against the packaged deliverable, not the source tree.
npx vitest run --config vitest.e2e.config.ts     # Reframe DOM e2e
# packaged smoke: _electron.launch({executablePath}) / pip install dist/*.whl in a fresh venv
```

### Diff-scoped coverage (optional, orthogonal)
```bash
# "Did the lines I changed get exercised?" — deterministic, reads coverage.xml vs the diff.
diff-cover coverage.xml --compare-branch=main
```

## How to use it in a turn

1. Identify the changed files.
2. Run **L0** on them. Fix lint/type errors first — they invalidate any test result below.
3. Run **L1** (`--testmon` / `related`). Capture the actual pass/fail output as evidence.
4. If the change is cross-cutting or you are about to claim task-complete / open a PR, climb to
   **L2** (via longrun) and check `.coverage-thresholds.json`.
5. If packaging / wiring / a user journey changed, climb to **L3**.
6. Report the highest rung you ran and its real output — `SUCCESS:<id> L1 12 passed` /
   `FAILED:<id> L1 2 failed …`. Never claim "tests pass" from L0 alone.

## Honesty rails

- **A green rung is not a green suite.** L1 asserts only "the impacted tests pass". If you claim
  *the change is verified*, name the rung you actually reached. A cross-cutting change verified
  only at L1 is under-verified — say so.
- **Selector fallback is a silent widener, not a narrower.** testmon with a missing db and
  `related` with an empty match both tend to run *more* (or, for `related`, *nothing*) — inspect
  the selected count; an empty L1 selection means "seed the db / check the path globs", never
  "there's nothing to run, ship it".
- **No ML selection.** If a tool proposes "predicted relevant tests" from a model, do not use it
  on this ladder — it can drop a covering test and manufacture a false green.

## Scope / non-goals

- Does **not** author tests — that is `tdd-workflow` / `test-driven-development` (write the test
  first, watch it fail). This ladder only *selects and runs existing* tests.
- Does **not** own coverage thresholds — `.coverage-thresholds.json` does.
- **Deferred (handBuild):** wiring the concrete L1 command into `ClaimWarningModule` /
  `claim_warning` so a "tests pass" claim is auto-annotated with (or checked against) the
  smallest-check command that was actually run. That integration ships separately and, per
  council C5, in **shadow mode** (observe/annotate only — never blocks, never nags). This skill
  is the deterministic-command reference it will point at.

---
*Evidence: gem-hunt-2026-07-12 MASTER decision queue, A-Tier2 "Smallest-check ladder L0->L3
(testmon / jest-related / diff-cover)", verification-gates streams #4/#5. Additive doc; ships no
gate. Deterministic dependency/coverage-map selectors only.*
