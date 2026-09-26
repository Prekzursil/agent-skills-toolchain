---
name: loop-supervisor-watchdog-gotcha
description: Why the SWFOC master ralph loop relaunched forever after completion,
  and the documented off-switch
metadata:
  node_type: memory
  type: feedback
  originSessionId: d0cfe3ce-69e6-41bb-8420-e52a4b0e04c2
permalink: main/claude-memory/downloads-swfoc-memory/loop-supervisor-watchdog-gotcha
---

The master ralph loop for swfoc_memory kept relaunching ~every 8 min even though
all 3 specs were at acceptance and `LOOP_COMPLETE` was on `STATUS.md`. Iters
580–588 misdiagnosed this as a "dropped `ralph emit LOOP_COMPLETE`" and re-emitted
9× with no effect.

**Real cause:** `ralph emit LOOP_COMPLETE` always succeeds — `ralph events` shows
`work.start → LOOP_COMPLETE → loop.terminate "Reason completed"` repeating 10+
times. `supervise_loop.sh` correctly stops on a deliberate exit 0. But the Windows
scheduled task `RalphSupervisorWatchdog` runs `.ralph/win_watchdog_check.ps1`
every 5 min, and that script only checks whether the supervisor PID is alive
(`kill -0 $supPid`) — it does NOT check `LOOP_COMPLETE`/`STATUS.md`. So it
resurrected the cleanly-stopped supervisor, which re-hit `LOOP_COMPLETE` and
stopped again → infinite cycle on finished work.

**Fix (iter-589):** create `.ralph/watchdog_disabled` — the documented pause flag
(`win_watchdog_check.ps1` lines 17 & 33). While present, the watchdog skips
relaunch, so a clean exit-0 stops the whole stack permanently. **Re-arm** by
deleting that file (watchdog relaunches within ~5 min, or run
`.ralph/start_supervised.sh`).

**Why:** completion-event re-emits can never beat an external relauncher; diagnose
the *relauncher*, not the emit. `ralph events --last N` is the fastest way to see
whether an emit landed.

**How to apply:** if a ralph loop appears "stuck completing," run `ralph events`
first. If you see repeated `LOOP_COMPLETE → loop.terminate`, the emit works — look
for a supervisor/watchdog (`.ralph/supervise_loop.sh`, `RalphSupervisorWatchdog`
scheduled task) and use `.ralph/watchdog_disabled` to pause it. Durable fix:
teach `win_watchdog_check.ps1` to treat `LOOP_COMPLETE` in `STATUS.md` (with no
open task) as terminal. See [[project_swfoc_re]]. Also note: the Bash-tool WSL
cannot see `/mnt/c` here — use Windows-native Read/Grep/Write/PowerShell.