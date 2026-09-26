---
name: bc-fsm-redesign
description: Ralph BC-unlock loop rebuilt as a deterministic phase state machine (implemented+committed;
  live cutover pending)
metadata:
  node_type: memory
  type: project
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/bc-fsm-redesign
---

The Ralph BC-unlock loop was redesigned into an ENFORCED PHASE STATE MACHINE to kill the stale cross-run short-circuit (the loop globbed old `reports/closer_decision_*.json` → instant fake `BC_UNLOCK_COMPLETE` at iter-1, never running the verifier). Full pipeline: superpowers brainstorming → design-review-gate (5 subagent reviewers, PASSED 5/5 after rev2) → writing-plans → plan-review-gate (3 adversarial reviewers, PASSED 3/3 after rev2). Branch `ralph-hardening`. Docs: `docs/plans/2026-05-24-ralph-fsm-redesign-{design,plan}.md` + `2026-05-24-fsm-cutover-runbook.md`.

ARCHITECTURE (in-Ralph; keeps supervisor/broker/watchdog):
`BOOTSTRAP→MEASURE_BASELINE→PLAN_UNLOCK→(unlock)→MEASURE_DELTA→{grew→PLAN_UNLOCK | flat≥N=3 valid + mitm&forge tried→DELIVER→MAINTAIN⟲}`; `status≠ok→re-MEASURE` (never counted).
- `.ralph/phase_controller.py` = SOLE transition authority + SOLE writer of `.ralph/state/phase.json` (run-scoped). Pure `decide(state,cumulative,gap,event)->Decision` (NO LLM judgment) + `run_controller()` I/O wrapper + `--bootstrap` CLI (archive prior reports + seed phase.json). 100% lines+branches (`.ralph/tests/`, gated by `.coverage-thresholds.json`). The killer-bug fix is a passing test: a fresh run (`valid_measures==[]`) CANNOT reach DELIVER at iter-1.
- Hats (`.ralph/hats/bc-unlock-master.yml`, 10): phase-controller + bootstrap (=old guardian+precondition; runs `--bootstrap` then `hgt_guard recover` + `precondition.py`) + verifier + planner + mitm/forge/tbcml/reanalyst (one per PLAN_UNLOCK via `current_surface`) + deliverer + refresh-watcher. `closer` + `archivist` REMOVED. Every action hat phase-gated (reads phase.json, no-ops off-phase). `ralph hats validate`=Valid.
- `.ralph/deliverer.py` (APK via tbcml `--bake` then copy to run-scoped name — tbcml_build.py has NO `--out`; + `coverage_report.md` 3 buckets + `operator_actions.md`; DELIVER+`_deliver_earned`-gated, no device-install verbs) + `.ralph/refresh_watcher.py` (clock-gated re-apply vs `deliver_baseline`, ~30min±jitter).
- `outer-supervisor.ps1`: `Get-LoopPhase` (FRESH phase.json read) replaces the closer/BC_UNLOCK_COMPLETE objective signal; `MAINTAIN`=healthy-idle, `DEGRADED`=alert.

STATUS (2026-05-24): WU1–6 implemented, tested, committed. A pre-cutover integration check FOUND+FIXED 4 bugs that would have produced a dead loop (phase.json path `root/state`→`root/.ralph/state`; `_fresh` phase→`BOOTSTRAP`; `bootstrap_state` resume→BOOTSTRAP-unless-MAINTAIN; bootstrap hat had NO phase.json seeding). **CUTOVER (WU7) NOT executed** — runbook ready (stop old loop, `archive_run` stale → `_run_pre-fsm`, relaunch `outer-supervisor.ps1`). Unverified-live: the HAT-runtime event-JSON build/emit flow + whether `ralph --continue` re-fires `bc.phase.bootstrap.start` (the resume trigger — needs observation; if not, add a supervisor kickoff emit). The OLD flawed loop is left running (harmless re-completion) until cutover. Relates to [[bc-verifier-robustness-fixes]], [[ralph-headless-mcp-trust-gate]].