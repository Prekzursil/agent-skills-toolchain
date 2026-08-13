# /rollback producer gap — deploy plan

DoD item 3 of lane HOOKRESEARCH. This lane wrote a plan rather than deploying, for one
reason stated up front: **closing the gap charges ~2.5 s to every Edit, Write and MultiEdit
in every session on this machine.** That is a latency decision on shared, currently-busy
infrastructure, not a bug fix, so it needs the owner's yes.

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

## The cost, measured

`command-center/hook-audit/_b8_rollback_cost.py`, throwaway repo, isolated checkpoint root:

| | ms | % of 15 s check budget | % of live 20 s PreToolUse event budget |
|---|---|---|---|
| cold (first call) | 5,486 | 36.6% | 27.4% |
| warm mean (4 calls) | **2,545** | **17.0%** | **12.7%** |
| warm max | 3,706 | 24.7% | 18.5% |

It fits both budgets with margin. The issue is not the budget, it is that this fires on the
most frequent tool call in a session, and each call also creates a `git stash` snapshot
object — so the ref namespace and repo size grow per edit. (This lane's earlier probe left
exactly one such ref: `refs/claude-checkpoints/t_14887964`.)

## Recommended sequence

**Step 0 — decide.** Owner picks one:
* **(a) Deploy as-is.** `/rollback` works again; every edit costs ~2.5 s.
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
`command-center/hook-audit/probe_hook_fleet.py --timing` and confirm the PreToolUse event is
still inside its live 20 s budget with the new check present. Expect the whole-event number
to move from 1,416 ms to roughly 4,000 ms.

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
