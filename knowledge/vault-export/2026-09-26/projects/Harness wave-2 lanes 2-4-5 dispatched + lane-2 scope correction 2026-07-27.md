---
title: Harness wave-2 lanes 2/4/5 dispatched + lane-2 scope correction 2026-07-27
type: note
permalink: main/projects/harness-wave-2-lanes-2-4-5-dispatched-lane-2-scope-correction-2026-07-27
tags:
- monitor-harness
- compaction-checkpoint
- wave-2
- '2026-07-27'
---

Continues [[main/projects/harness-wave-2-grill-decisions-2026-07-26-wfmon-mcp-gui-agent-native-ultracode-rails]] and [[main/projects/harness-wave-2-first-landing-pr-224-two-signal-stall-fix-merged-deployed-2026-07-27]].

## LANDED on origin/main (1728162) this session
- **#227 `tools/agentspec`** (44 files) — the portable spec + shared observation envelope + the
  dispatch-safety pure core (argv/prompt transport, completion AND-gate, progress-stream rejection,
  terminal markers, budget accounting, determinism) + a hermetic eval registry. This IS lane 3's core.
- **#228 `tools/mcpctl`** (23 files) — READ-ONLY MCP inventory + health matrix + CLI.
- **#230** stub-ledger wrapped-comment false positive (use-vs-mention in the scanner itself).
- Both #227/#228 needed a manual `quality.yml`+`charter.yml` conflict resolution — they append to the
  same regions. Resolution = keep BOTH sides; charter prose merges into one list. `charter_check.sh`
  is wired at `quality.yml:66`, so a green CI run mechanically proves the closed-gate-set rule held.

## Verifications I ran myself (the repair agents' receipts never returned)
- **#227 B-1 RED-check**: mutating `MIN_SUBSTRING_SCAN_LEN` 64->4096 now breaks **7 tests** where
  pre-repair it broke **ZERO** (366 passed). Restored -> 406 passed, clean. The pin is real.
- **#228 redaction ordering**: `safe()` must `strip_controls` BEFORE `redact_text`. Pre-fix, 20/20
  token-shape x separator combinations leaked verbatim through the CLI. Fixed + parametrised
  interleaved matrix + a `safe-order-swapped` mutation row.

## CORRECTION — I had lane 2 badly under-tracked
The grill note is explicit: lane 2 needs **four capability groups across three surfaces** —
health matrix · live enable/disable/reconnect · add/remove/edit configs · curation + token/RAM
budgeting with impact preview, delivered as cockpit pane + localhost web GUI (stdlib http.server) + CLI.
`mcpctl` shipped only the **health matrix + CLI** = roughly one of four groups, one of three surfaces.
I had been treating lane 2 as DONE. It is ~25% done.

Also corrected: **there is no `workflow_run.py` and no `FleetPoller` symbol** anywhere in monitorcore
— an earlier note of mine said the wfmon panes should "reuse workflow_run.FleetPoller". That symbol
does not exist; the real refresh mechanism lives in `cockpit.py`/`monitors.py`/`view.py`.

## Lane-4 transport question — SETTLED, and the critic's premise was refuted
A plan-gate finding argued agentspec must admit an `argv` prompt transport because the `agy` rail
needs it ("CONFIRMED by PROBE-11b/11c"). **Refuted by `RAIL-PROBE-2026-07-26.md`**: agy's `--version`
TIMED OUT at 15s -> headless **UNVERIFIED**. Shipped agentspec has
`PROMPT_TRANSPORTS = ("file","stdin")` (`argv.py:34`) and classes `PromptOnArgv` a hard
`policy-violation` (`argv.py:42`). That is CORRECT policy — widening it would reintroduce the measured
`os error 206` (payload_len=34472). Rails needing argv must SPILL to file/stdin.

## Three lanes dispatched in parallel (each: scout -> build -> N adversarial critics -> repair)
- `wf_473ce16b-057` **lane4-agentrail** — generic config-driven rail CONSUMING agentspec. Worktree
  `~/source/ast-l4-agentrail`, branch `lane4/agentrail`. Owns the `quality.yml` edit this wave.
- `wf_9c2fbf3a-329` **lane5-wfmon-panes** — Phase-2 WU9-13 switchable panes in monitorcore. Worktree
  `~/source/ast-l5-wfmon`. NO quality.yml edit (monitorcore already gated). Owns the cockpit MCP pane.
- `wf_e8f7150d-986` **lane2-mcp-control** — the 3 missing capability groups + stdlib web GUI as a NEW
  sibling package (mcpctl is read-only BY CONSTRUCTION — its tests AST-assert no write call, so
  mutation must not go there). Worktree `~/source/ast-l2-mcpctl-apply`.

## Workflow reliability fix (root cause of the previous run's silent holes)
The earlier build workflow used `pipeline()`, where **a stage that throws drops the item to null and
silently skips its remaining stages**. That is exactly why `build:L4-agentrail`, `critic:L4`,
`recritic:L2` and `recritic:L3` "never started" — no error surfaced, the lane just vanished. All three
new workflows wrap every agent call in a `safe()` helper that catches, `log()`s, and returns a
sentinel, so a dead agent degrades one stage instead of deleting a lane.

## Standing done-bar (owner, non-negotiable)
100% coverage gate -> **fresh independent critic PASS** -> merge -> **additive deploy** -> **E2E verify**.
The deploy+E2E half is mine to run after each merge; a merged PR is NOT done.
