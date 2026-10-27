---
name: smallest-check-ladder
description: Use when you need to run "the smallest test that could still catch this change" instead of blindly running the whole suite (or nothing). Provides an invocable L0 to L3 ladder — L0 lint the edited file, L1 impacted tests via deterministic selectors (pytest --testmon / jest or vitest related), L2 full suite via longrun, L3 e2e — so a claim of "tests pass" is backed by a proportionate, real check. Deterministic dependency and coverage-map selection ONLY; never ML "predictive test selection". Triggers include "run the relevant tests", "smallest check for this diff", "which tests cover this file", "is it worth running the full suite". NOT for authoring new tests (use tdd-workflow) and NOT a coverage-threshold gate (that stays .coverage-thresholds.json).
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

### Concrete commands
### L0 — edited-file lint / typecheck
### Python (Reframe: ruff + basedpyright)
### TypeScript (Reframe app/)
### L1 — impacted tests (deterministic selectors)
### Python — pytest-testmon: selects tests whose recorded coverage touches the changed code.
### Deterministic: it replays a stored per-test coverage map, it does not predict.
### JavaScript/TypeScript — dependency-graph selection (deterministic: static import graph)
### L2 — full suite (always via longrun; it exceeds 60s)
### Wrap in longrun per the >60s rule; never a blocking foreground call.
### TS:
### L3 — e2e against the built artifact
