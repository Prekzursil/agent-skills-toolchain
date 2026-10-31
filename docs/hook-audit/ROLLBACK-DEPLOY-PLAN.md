---
title: ROLLBACK-DEPLOY-PLAN
type: note
permalink: dqverify-repo-20261013/docs/hook-audit/rollback-deploy-plan
---

# /rollback producer gap — deploy plan

DoD item 3 of lane HOOKRESEARCH. This lane wrote a plan rather than deploying, because
arming a PreToolUse hook is a latency decision on shared, currently-busy infrastructure,
not a bug fix, so it needs the owner's yes.

> **ROUND-3 CORRECTION — the sentence that used to stand here is REFUTED and kept.** It read
> *"closing the gap charges ~2.5 s to every Edit, Write and MultiEdit in every session on
> this machine."* Both halves were wrong. **Frequency:** `checkpoint.py:208-211` keys a
> snapshot on `f"{turn}|{repo}"` and early-returns when it is already present, so the
> snapshot is taken **once per human turn per repo**, not once per edit. **Magnitude:** the
> 2,545 ms it quoted was the mean of four calls that took that early return -- the round-1
> probe sent five identical payloads with no `transcript_path`, so they shared one turn key,
> and its own committed evidence said `index_records: 1` beside five samples. Re-measured
> with the two paths separated and a fail-closed control, the snapshot path runs at a median
> <!-- cite: id=R3-b8-med file=B8-ROLLBACK-COST.json path=first_in_turn_median_ms value=369.2 tol=0.001 -->
> **369 ms** and the early return at
> <!-- cite: id=R3-b8-sub file=B8-ROLLBACK-COST.json path=subsequent_median_ms value=194.6 tol=0.001 -->
> **195 ms** on a quiet box. See `ROUND3-CORRECTIONS.md` R3-3 for why those are ~7x below the
> round-1 readings and what part of the decision that does NOT change.

## What is broken

`commands/rollback.md` promises a checkpoint before every edit and reads an index that no
live hook writes. Both sides were fired independently, which is what separates "producer
broken" from "producer dark":

| fact | state | how it was established |
|---|---|---|
| producer `hooks/edit-checkpoints/checkpoint.py` works | **YES** | fired into an isolated `EDIT_CHECKPOINTS_DIR` asserted empty first → wrote `index.ndjson` (1 record) + 1 real git-stash snapshot ref, exit 0 |
| wired in the REPO manifest | YES | `hooks/_dispatch/manifest.json` → PreToolUse, `timeout: 15`, matcher `Edit\|Write\|MultiEdit` |
| wired in the LIVE manifest | **NO** | live `_dispatch/manifest.json` holds 25 checks, repo holds 27 |
| wired in live `settings.json` | **NO** | 42 entries enumerated; not among them |
| consumer index freshness | **dead** | 944 records / 13 sessions, newest `2026-07-18 00:24` |

So `/rollback` worked until 2026-07-18 and has silently returned nothing since. The second
repo-only check, `mcp-liveness/pretool`, has the same status and smaller blast radius.

**Name the class, not just the instance:** moving a hook from a `settings.json` entry into
`_dispatch/manifest.json` unwires it until the manifest is deployed, and **nothing notices**.
`hooks/_dispatch/test_bootstrap_deploy_completeness.py` is CI-wired and green, but by its own
docstring it checks `bootstrap.ps1` against `agent-self/config/` — a repo-internal invariant.
CI on a Linux runner has no `~/.claude`, so it structurally cannot see repo→live drift.

## The cost, measured — two paths, not one

`command-center/hook-audit/_b8_rollback_cost.py --repeat 12`, throwaway repo, isolated
checkpoint root. The probe now runs the two code paths as separate phases and **refuses to
publish** unless it can prove they are different paths: the armed phase must write one index
record per call and the repeat phase exactly one in total.
<!-- cite: id=R3-b8-ctl file=B8-ROLLBACK-COST.json path=control_phases_distinguished value=True -->
That control passed (
<!-- cite: id=R3-b8-armed file=B8-ROLLBACK-COST.json path=armed_index_records value=12 -->
12 records armed,
<!-- cite: id=R3-b8-rep file=B8-ROLLBACK-COST.json path=repeat_index_records value=1 -->
1 on repeat).

| path | when it is paid | median | max | max % of 15 s check budget |
|---|---|---|---|---|
| **first edit in a turn** (snapshot) | once per turn per repo | 369 ms | <!-- cite: id=R3-b8-max file=B8-ROLLBACK-COST.json path=first_in_turn_max_ms value=596.3 tol=0.001 -->597 ms | <!-- cite: id=R3-b8-maxpct file=B8-ROLLBACK-COST.json path=first_in_turn_max_pct_of_check_budget value=4.0 tol=0.001 -->**4.0%** |
| **every other edit** (early return) | all remaining Edit/Write/MultiEdit | 195 ms | 271 ms | <!-- cite: id=R3-b8-subpct file=B8-ROLLBACK-COST.json path=subsequent_max_pct_of_check_budget value=1.8 tol=0.001 -->1.8% |

**What is stable and what is not.** Three runs of this probe on this box have produced
5,486 / 7,428 / 597 ms as the worst sample — a 12x spread driven by machine load (round 1
and the verifier both ran with nine lanes mid-wave; this one did not). **The latency figure
is therefore a range, not a constant: ~0.3 s quiet, up to ~7.4 s under a full wave.** The
*decision*, however, does not move: even the worst sample ever recorded is 49.5% of the 15 s
check budget, so `verdict_fits_budget` is
<!-- cite: id=R3-b8-fits file=B8-ROLLBACK-COST.json path=verdict_fits_budget value=True -->
true under every condition measured. Quote the range, not one draw from it.

The residual concern is unchanged and is NOT about the budget: each snapshot creates a
`git stash` object, so the ref namespace grows — per *turn*, now that the frequency is
correctly stated, rather than per edit. (An earlier probe left exactly one such ref:
`refs/claude-checkpoints/t_14887964`.)

## Recommended sequence

**Step 0 — decide.** Owner picks one:
* **(a) Deploy as-is.** `/rollback` works again. Cost: one snapshot per turn per repo
  (~0.4 s measured quiet, up to several seconds under load) plus ~0.2 s on every other edit.
* **(b) Deploy narrowed.** Add an `if` field / tighter matcher so checkpoints are taken only
  for edits under the paths worth rolling back. **0 of 42** live entries currently use the
  vendor `if` field, so this mechanism is unused estate-wide and would be a first.
* **(c) Do not deploy; fix the promise instead.** Amend `commands/rollback.md` to say the
  producer is unwired, so the command stops promising what the harness cannot do. This is the
  honest zero-latency option and should be the default if (a)/(b) are not chosen this round.

Whichever is chosen, **do not leave it as-is**: today a command promises a capability that
has not existed for ~26 days, and that is the worst of the three states.

**Step 1 — deploy ONLY the manifest.** Copy `hooks/_dispatch/manifest.json` (and the two
hook trees if absent) repo → `~/.claude/hooks/`. Verify with the existing differ,
`command-center/probe_hook_manifest_drift.py`, which already reports both directions — do not
write a second one.

**Step 2 — DO NOT bootstrap `settings.json` from the repo.** Measured by the grounding lane:
repo `agent-self/config/settings.json` is missing the live-only `SessionEnd:session-end`,
`PreToolUse:workflow-monitor-autolaunch` and `UserPromptSubmit:semantic-router` entries, so a
repo→live settings deploy would **delete the entire `SessionEnd` event**. That axis has no
checker today.

**Step 3 — re-measure, do not assume.** After deploying, run
`command-center/hook-audit/probe_hook_fleet.py --timing --repeat 3` and confirm the
PreToolUse event is still inside its live 20 s budget with the new check present. *(Round-3
correction: the previous sentence here predicted the whole-event number would move "from
1,416 ms to roughly 4,000 ms". That extrapolated the refuted ~2.5 s per-edit figure. On the
corrected numbers the added cost is ~0.4 s on the first edit of a turn and ~0.2 s after — but
both terms scale with box load, which is exactly why this step says measure rather than
predict. Do not replace the prediction with a new prediction.)*

**Step 4 — gate the class.** Wire `probe_hook_manifest_drift.py` as a LOCAL pre-deploy gate
(it cannot run on a GitHub runner — no live tree) and extend it to the
`agent-self/config/settings.json` ↔ live axis from Step 2, which currently has no checker.

**Rollback of this deploy:** restore the previous live `manifest.json` (25 checks) and
re-run the differ. The producer is additive and holds no state the rest of the fleet reads,
so removing it cannot break another check — only `/rollback` goes back to returning nothing.

## Also fix while you are in the manifest

The manifest's `settings_timeout` disagrees with live `settings.json` for two events —
PostToolUse 15 vs 25, PreToolUse 15 vs 20 — so the manifest documents budgets that are not
enforced. `command-center/fix_hook_timeouts.py` already exists for surgical timeout edits
(textual, deliberately never round-tripping the JSON, because the first version reformatted
296 lines). Use it rather than editing by hand.