---
title: Program R autonomous research loop 2026-07-26
type: note
permalink: main/projects/program-r-autonomous-research-loop-2026-07-26
tags:
- program-r
- harness
- security
- codex
- databricks
- autonomous-loop
---

# Program R — autonomous research loop (2026-07-26)

500-unit Codex (`gpt-5.6-sol`, `service_tier=priority`, `danger-full-access`) fan-out on
Databricks researching the harness (`~/.agents/harness`) + `agent-skills-toolchain`.
Built in `~/source/csie-foundation-wt`, branch `feat/csie-foundation`, commit `22ee2a5`.

## What it is

- `harness/lanes/research.py` — READ-ONLY lane, (target x lens) units, 8 lenses.
  A shared prompt would make 500 units 500 duplicates, so the lens reaches the prompt text.
- `e2e/build_research_targets.py` — TIERED plan (`_R_plan.json`). Budget is spent by tier,
  not spread evenly: harness 12x8 + hooks 38x6 = 65% of the 500.
- `e2e/run_research.py` — 11 shards of 48 (R9 caps a wave at 48). Omitting `--quota-ok` REFUSES.
- `e2e/my_active_runs.py` — counts ONLY `codex-fanout-*` runs.
- `e2e/watch_research.sh` — monitor; emits DONE/FAILED/STALLED so silence != progress.

## Traps that cost real time (do not re-walk)

- **Bolt Databricks is a SHARED PRODUCTION workspace.** `jobs list-runs --active-only`
  returns `fraud_driver`, `payment_method_payments`, `business_payment`. Gating a wave on
  workspace-wide idleness NEVER releases — the shard chain silently never launched. Always
  filter by run name. Measured: 0 mine vs 18 workspace.
- **One batch = ONE Databricks run**, not N. `submit.submit()` returns a single run_id for
  all 48 units; the run is named `codex-fanout-n<N>-c<C>`.
- **The harness is mirrored at `ci/harness/`, NOT `.agents/harness/`.** Checking the latter
  and concluding "absent from origin/main" was wrong. The mirror is also PARTIAL (8 of 12
  modules) and STALE (adapters.py differed by 328 lines), so shipping a DBFS bundle was
  still correct — for a different reason than first stated.
- **Gated counts are NON-MONOTONIC while a wave is live** — write-as-you-go rewrites drop an
  artifact below the 1024-byte floor mid-milestone. Only the drained state is meaningful.
- Severity inflation is real: ~84% of units returned HIGH. Treat HIGH as "worth reading";
  trust only findings carrying an executable reproduction.

## Confirmed defects (each independently reproduced BEFORE fixing)

1. **camelCase tool payload bypassed the destructive-command guard** — PR #221.
   `HARNESS_LIFECYCLE_GUARD=1`, `rm -rf /tmp/victim`: `tool_name`/`tool_input` -> `deny`;
   `toolName`/`toolInput` -> **ALLOW**. `normalize_event` was alias-tolerant everywhere
   (`tool_use_id`/`tool_id`, `task_name`/`taskName`) EXCEPT the two fields the guard reads.
2. **JSON-quoted credentials bypassed redaction** — PR #222.
   `password=abc...` caught; `{"password":"abc..."}` returned BYTE-FOR-BYTE. After the key
   comes a quote, in neither `[A-Za-z0-9_-]` nor `\s`, so `[:=]` never matched. Also
   `password=!Correct...` (punctuation excluded from the value class) and `Basic` auth
   (only `Bearer` was covered). Matters because `redact_text` guards `set_goal` before it
   persists to the event ledger. Over-redaction after the fix measured at 0 of 8.
3. **One session's pre-compaction context injected into another** — PR #220.
   `compact-restore.ps1` took the newest snapshot in the dir and fell back to the shared
   global `~/.remember/tmp`; snapshots were named by timestamp only (session_id was captured
   but written only to `compaction-log.jsonl`).

## Refuted — do NOT re-raise

- **Goal-bleed between sessions via the harness ledger: REFUTED.** Every live caller passes
  `session_id`; peer sessions read `''`. `goal(cwd, None)` falls back to a shared slot and
  that slot IS polluted, but no live consumer calls it.
- ~~`sessionstart-replay.py` is unregistered, so latent~~ **THAT CALL WAS WRONG — CORRECTED.**
  It IS registered, in the REPO: `agent-self/config/settings.json:162` (repo declares 5
  SessionStart hooks, live `~/.claude/settings.json` declares 3 and omits it). I checked only
  the LIVE file, found it absent, and concluded dead code. A research unit read the repo copy
  and caught it. So the cross-session goal leak was **armed in the repo and dormant on this
  box only by drift** — the next deploy re-introduces it. Fixed in PR #223 (goal line removed
  from all three copies; decisions/failures/milestones kept, since those are durable project
  history and legitimately shared).
  **Lesson: "not wired" must be checked in the REPO, not just live — deployed config is what
  ships. Drift can disarm a defect locally and hide it.**

## The now.md bloat — full causal chain

`remember` consolidation logs `skip` every run -> its haiku summariser never populates
staging -> it shells to headless `claude`, which costs **80-169s here for a trivial prompt**
-> against a **hardcoded 120s** timeout (`pipeline/haiku.py`, no config key) -> `now.md`
grew to 774 KB (182 entries; 16 outliers held 89.8%, 9 duplicate groups wasted 27.3%;
median entry was a correct 401 B).

Fixed by rotation: 774,458 -> 31,500 B, byte-identical backup + 122-entry archive, nothing
deleted. Durable via the `RememberBufferRotate` daily Scheduled Task
(`~/scripts/rotate-remember-buffer.py`, no-ops under 120 KB).

**Refuted:** that the bloated buffer caused the slow startup — post-rotation startup measured
169s, SLOWER than the 80s before. The slowness is load-dependent, not buffer-dependent.

**Scheduled-task trap:** a task action shelling through `cmd.exe` purely to redirect stdout
hung at 0% CPU on malformed nested quoting. Have the script write its own log and invoke
python directly.

Relates to [[reference_fleet_alert_campaign_gotchas_2026-07-25]] and the CSIE coverage lane.
