---
title: Claude Code background watchers die on auto-compaction, NOT from the scheduled
  reapers
type: note
permalink: main/reference/claude-code-background-watchers-die-on-auto-compaction-not-from-the-scheduled-reapers
tags:
- harness
- claude-code
- background-tasks
- compaction
- reaper
- monitoring
- gotcha
---

**When a Claude Code background Bash/ssh watcher (a `run_in_background` monitor) keeps dying, the cause is Claude Code's own auto-compaction terminating background tasks — NOT a process reaper. Do not chase or disable the reapers; it's a dead end.**

Verified 2026-07-11 by reading the actual kill-logs of every reaper on this Windows machine:
- **RAM-Keeper** (scheduled task, every 10 min, `C:\Users\Prekzursil\scripts\ram-keeper.ps1`): `reaped=0` across 300+ runs over two days. Only targets `node.exe`/`python.exe` — orphaned AUDIT dev-servers (reframe-copy / vite.renderer.audit / ng coverage) and orphaned MCP stdio servers — and PROTECTS anything whose ancestry reaches a live `claude.exe`/shell/OS-root anchor. The one non-zero run killed 6 orphaned *biomni python* MCPs, never a bash/ssh proc.
- **MCP-Orphan-Reaper** (`C:\Users\Prekzursil\scripts\mcp-reaper.ps1`, every 30 min): `reaped 0` every run; node/python only.
- **resource-guard.ps1**: log/propose only ("NEVER reaps/kills"). **cs-watchdog.ps1**: only recovers the WSL Claude-Science daemon. **bg-registry** hooks: reader-only.

**None of them can touch a `bash.exe`/`ssh.exe` watcher.** Deaths correlate with session compaction (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70` on this box): the first watcher survived ~2 h until a compaction, later ones died within minutes as context filled faster.

**How to apply:** if a background monitor dies, do NOT re-investigate/disable RAM-Keeper or MCP-Orphan-Reaper — assume compaction and switch to a compaction-proof mechanism, see [[Compaction-proof long-monitoring — ScheduleWakeup + on-box handlers, not Windows background watchers]]. A genuinely different/older reaper may have existed and been retired; if the user names a specific one, check its log directly before acting.