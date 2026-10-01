---

## 10. Replay/resume, null-result, safeguard-kill and concurrency handling

### 10.1 Replay and resume (F-43, F-47, T-14..T-16, S-18; J2 gaps 1, 3, 6, 7; J1 CG7/CG8; C-8, C-22)

- **Two resume modes, chosen by `args.resume_mode`.** `git` (default): every invocation is a fresh workflow run; the setup prompt carries `launched_at`, so the probe is live; correctness and most of the speed come from git-state idempotency (author/builder `status:'reused'` on an existing green branch; integrator `already-merged` **with evidence** — the head must be unchanged, the gate exit 0 with its digest and the pinned gate sha, cherry/patch-id assertions empty (C-20); merged set from `plan/status/*.json` on the integration branch AND `git ls-tree`). `cache` (`{scriptPath, resumeFromRunId}`): allowed only after the smoke run's settling experiment (§2.0 step 7) showed that unchanged replays hit and a non-prompt knob change still hits; the setup prompt then omits `launched_at`. **Correctness never depends on the cache** (C-R): a stale cached sha is caught by `missing-ref` at merge time and re-driven with a `redrive:` suffix; `integration_sha_at_launch` is checked by the script against the live head (throws `stale-launch-args`).
- **Prior rows are detail, never truth (C-8).** On resume, a prior `parked` row is re-driven automatically when its reason matches `RETRYABLE_RE` (`agent-null`, `threw`, `timeout-or-dialog`, `not_attempted:…`, `starved:…`, `integration:not-merged:null`, `fixcards-unavailable`) — nobody ever judged that work; it stays parked otherwise and is re-driven only when named in `args.retry_parked` (the checkpoint's `retry_parked_suggested` computes exactly this list: parked rows whose reason is retryable). `not_attempted`, `blocked_on_owner`, `dropped_null` and `reverted` prior rows are never adopted — they are re-evaluated live. `last_clean_gate` seeds `lastClean` only when its head equals the live integration head.
- **Timeout ↔ replay divergence (J2 gap 1).** A timed-out call may still journal a result; on a cache resume it would return instantly and the retry branch would be skipped. Mechanism: any `timeout-or-dialog` receipt sets `REPLAY_RISK`, and `next_args.resume_mode` becomes `'git'` for the following invocation.
- **Completion-order call sequence (J1 CG8).** Barrier waves keep control flow independent of completion order at the wave level; inside a wave the two chains' `agent()` calls still interleave by completion — harmless in `git` mode, one more reason `cache` mode is opt-in.
- Every prompt is a pure function of `args` and prior results; arrays sorted by id before `JSON.stringify`; the ledger summary in the synthesizer prompt is sorted by `(role, mode, id, attempt)` (J2 gap 11); the integration head appears in every code-reading prompt; no timestamps except `launched_at` in the git-mode setup prompt.
- **Lifetime cap.** Replayed calls are assumed to count (J2 gap 3); `max_agents_this_run` slices with a per-chain reservation of 7 keep every invocation ≤ 110 agents at cap 2; in `git` mode each invocation is its own workflow run.

### 10.2 Null results (F-41, T-17, D-21; C-11, C-7)

Every `agent()` goes through `run()`: ledger row for every call including `null`/`threw`/`timeout-or-dialog`; one narrower retry (`attempt: 2` + `NARROW`); then a typed `{status:'null', reason}`. Downstream typing is per consumer, never a global revert: **a clean-gate null or malformed return is `gate-unavailable`** — the three-way type is `pass | fail | gate-unavailable` and only a genuine `fail` may revert (a wrong head, a missing digest, a contradictory self-test or a malformed shape is `unavailable`, never a revert, C-11); **a veto null is `veto-unavailable`** (not satisfied — fail closed); **an evidence null is `evidence-unavailable`**. A `threw` receipt whose detail matches the budget ceiling sets `HALT='budget-exhausted'` immediately (no retry, no fan-out of instant throws — J2 gap 8). Barrier results are never `.filter(Boolean)`-ed without a counted log line (lens drops, refute chain drops, wave chain drops). `pipeline` stage throws are caught inside `buildTask` and typed `threw`. **The synthesizer is exempt from the HALT branch and from the budget-reserve guard** (C-7/F-45: the reserve exists to pay for it, so it runs after every HALT and even on an exhausted budget; the invocation agent cap still applies to it).

### 10.3 Safeguard kills (F-31, F-42)

Hardening cards 09a/09b/09c and the persona card carry reading lists ≤ 6 files and defensive framing; their verifiers run at `xhigh`; builders commit per coherent step; the retry prompt begins with the salvage rule; two nulls → `blocked:'agent-null:<role>'`. `model` is never overridden (the session model is the model that succeeded on retry in the observed run); if the orchestrator ever launches on a different session model, adding `model` means editing the script AND the `meta.phases` Build entry (J2 gap 10) — a checklist item, not an arg.

### 10.4 Concurrency and timers (F-44, T-7, T-8; J2 gaps 2, 4, 9)

- `args.wave_size ≤ args.cap` is asserted at script start and the setup probe's `nproc` must give the same cap (`cap-mismatch` throws — J2 gap 9). Each chain is strictly serial, and **the wave itself is recomputed from the live status map after every wave** (C-5: a card whose dependency parked is never scheduled), so a wave never enqueues more than `wave_size ≤ cap` agents: **no FIFO queueing in Build**. Where a barrier does exceed the cap (3 review lenses at cap 2; the R0 trio + pre-verifiers), `tmo(mode, enqueued)` multiplies the base timeout by `ceil(enqueued / cap)` so queue wait cannot fire a timer on an agent that has not started (J2 gap 2).
- Base timeouts: author 25 min, red 10, build 50, fix 40, verify 30 (mutants + revert-proof added), merge 20, conflict 30, clean 25, journeys 25, review 30, refute 15, veto 25, plan 40, setup 30, synth 15, synthfix 10, fixcards 10.
- **Permission dialogs vs hangs (J2 gap 4).** The script cannot see a dialog. Mechanism + owner checkpoint: the smoke run (one card, owner attending) records the permission inventory into the allow-list before any full invocation; the runbook requires the owner to stay attached during the first wave of every invocation; a `timeout` receipt is logged as `timeout-or-dialog` and never retried more than once.
- The script logs per wave: cards built/blocked, merges with their merge shas, the stop reason, and the remaining waves.

### 10.5 Outward actions, toolchain and remotes (F-1, F-35; C-17)

`assertCommon` on every return: `repo_toplevel` must be the build repo or a path under `<repo>-wt/` (prefix test, J1 D1) and `git_common_dir` must be `<repo>/.git`; a non-empty `outward_actions_taken` sets `HALT` (every later `budgetOk()` is false; the synthesizer still runs; the checkpoint is `failed` with `halt`); the setup probe and every clean gate report `git remote -v` (non-empty without approval → `HALT`) and the toolchain status hash — computed as `git status --porcelain -- . ':!docs/grills'` on the toolchain repo, because the owner's grill sync loop legitimately writes `docs/grills` every five minutes and that is not a mutation of the executed fleet (C-17); a mismatch → `HALT`.

### 10.6 Secrets in structured returns (J1 CG3)

`redact()` walks every string in a return (depth ≤ 6) with `SECRET_RE`, replaces matches with `[REDACTED]`, logs the fact (never the value) and marks the return; `taskDone()` condition 11 blocks the card (reason `secret-shaped-output`, no fixer is launched); the fixer never receives an unredacted string; the synthesizer prompt carries only sorted ledger summaries and script-computed rows. The prompts additionally warn that dummy credentials must not match the secret regex (`TESTTOKEN-…`, never `hf_`/`ghp_`/`sk-ant-` with 20+ characters — C-32), so a fixture cannot park its own card.

---

## 11. Budget and effort plan by role; estimated agent counts and wall-clock (recomputed for v2)

| Role · mode | effort | timeout (base) | est. duration (UNVERIFIED extrapolation) |
|---|---|---|---|
| integrator · setup (+ live probe) | medium | 30 min | 10-15 min (first invocation), 3-5 min after |
| verifier · preverify (×5, R0) | medium | 20 min × queue factor | 6-10 min each |
| planner · api-ledger / verifier · catalog (R0) | medium / low | 25 / 15 min | 10-15 / 5-8 min |
| planner · plan (+ repair re-run) | high | 40 min | 15-25 min |
| verifier · plan / index | medium / low | 20 / 10 min | 8-10 / 2 min |
| author · tests / journeys | medium | 25 min | 8-12 min |
| verifier · red | low | 10 min | 3-4 min |
| builder · implement / fix | high | 50 / 40 min | 15-25 (S) · 25-40 (M) / 10-20 min |
| verifier · verify (gate + DoD re-runs + mutants + revert-proof + apicheck-extended + diff_stats) | medium (xhigh on security) | 30 min | 10-14 min |
| integrator · merge / ff / revert | low | 20 / 15 / 15 min | 3-5 min |
| integrator · conflict | high | 30 min | 10-15 min |
| integrator · clean-gate (`--self-test --journeys`) | low | 25 min | 8-11 min |
| integrator · fixcards | low | 10 min | 1-2 min |
| verifier · review (lens) / refute / veto | high / medium / xhigh | 30 / 15 / 25 min | 12-15 / 4-6 / 8-10 min |
| synthesizer · report / fix | low | 15 / 10 min | 5 / 2 min |

**Agent count (22 cards; fix mix re-derived honestly in v2.1 (V-10): 5 base + 0.4×2 (one fix) + 0.15×4 (two fixes) + 0.1×2 (author re-drive) + 0.05×1 (null retries) ⇒ ≈ 6.65 agents per card; the v2 confirm-RED two-execution rule and author re-drives (C-26) are inside that mix):** R0 = setup 1 + pre-verify 5 + api-ledger 1 + catalog 1 + planner 1 + plan check 1 + synth 1 = **11**, plus a repair re-run (+2: planner + plan check) when the plan needs repair. R1 = cards 22 × 6.65 ≈ 146 · merges 22 + conflicts ~3 + ff ~3 = 28 · clean gates ≈ 13 waves + ≈ 2 review pre-checks (C-10: only when the last clean gate is not a pass at the current head) ≈ 15 · journeys authors ≈ 6 + their merges 6 · setup + index per invocation ≈ 4 × 2 = 8 · review 3 rounds × 3 lenses = 9 · refuters ≈ 13 · fixcards integrator calls ≈ 3 · fix cards ≈ 7 × 6.65 ≈ 47 + merges 7 + clean gates ≈ 8 · veto 3 · synth ≈ 4 + fix ≤ 4 → **≈ 296 (range 280-315)**. R2 ≈ 27-32, R3 ≈ 9. Total across all runs ≈ **335-350**; every invocation ≤ 110 agents (slice) at cap 2 — far inside the 1000 cap even if replays count. Versus A3's ≈ 240: +≈ 35 for the R0 trio + pre-verifiers, journeys per seam wave, self-tests, the synth-fix probe, fixcards calls and review pre-check clean gates.

**Wall-clock (per-card chain without a fix ≈ author 10 + red 3.5 + builder 20 + verify 12 ≈ 46 min; with one fix ≈ 78 min; wave ≈ slowest chain + serial merges × 4 min + clean gate 10 min + journeys 12 min on the seam waves):**

| | cap 2 (this box) | cap 14 (after the resize) |
|---|---|---|
| Waves | ≈ 13 (22 cards, width 2, runtime DAG) | ≈ 10 (DAG depth; width 1-4 per level) |
| Build + integrate | ≈ 13 × ≈ 95-100 min ≈ 21-22 h (serial merges + clean gate + seam-wave journeys; v2.1 V-10 re-derivation) | ≈ 10 × ≈ 100 min ≈ 16-17 h (the slowest chain in a wide wave + more merges) |
| Review loop (3 rounds, ~7 fix cards + fixcards commits) | ≈ 5-6 h | ≈ 3 h |
| Setup + plan + synth (per invocation) | ≈ 2 h over 4-5 invocations | ≈ 1.5 h over 2-3 invocations |
| **Total R1** | **≈ 28-29 h, run as 5-7 resumable invocations (`max_agents_this_run` 110 ≈ 5.5 h each; v2.1 V-10: one more invocation than the v2 estimate) with owner stops at fixture #1, the boundary fixture and the worker decision** | **≈ 20-22 h in 2-3 invocations** (the same owner stops apply) |

Honest reading: versus A3 the grafts add ≈ 4-5 h at cap 2 (mandatory mutants + revert-proof per card, `--self-test` on every clean gate, journeys per seam wave, the pre-verification trio, the review pre-check clean gates, fixcards commits, author re-drives) and the fixture-#1 precondition adds one owner stop that A3 did not have. These remain UNVERIFIED extrapolations from A3's observed per-role durations — the v2 drive runs a fake harness and yields no timing evidence. The cap buys width, not depth: the DAG is 9-10 deep and the API lane cannot be deferred (G-3), so the critical path is the plan's. `budget.total` may be `null`; counters are the first guard, the reserve the second, `HALT` the third; **the synthesizer always runs** (it is exempt from the reserve guard precisely so the reserve can be spent on it).
