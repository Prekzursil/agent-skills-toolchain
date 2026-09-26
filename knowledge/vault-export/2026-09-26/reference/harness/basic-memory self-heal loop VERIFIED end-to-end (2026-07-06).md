---
title: basic-memory self-heal loop VERIFIED end-to-end (2026-07-06)
type: reference
permalink: main/reference/harness/basic-memory-self-heal-loop-verified-end-to-end-2026-07-06
tags:
- basic-memory
- harness
- self-heal
- liveness
- spool
- verified
---

# basic-memory "always up" loop — VERIFIED working end-to-end (2026-07-06)

User asked "is basic-memory working? make sure it always is." Verified the full self-heal loop is real,
wired, and DEMONSTRABLY fired this session (down -> auto-restart -> spool-replay -> no data lost). No action
needed — it works.

## The loop (all pieces confirmed present + wired)
- DETECT: `~/.claude/hooks/mcp-liveness/liveness.py` probes 127.0.0.1:8765 via MCP handshake. Wired in
  settings.json on SessionStart (`liveness.py sessionstart`, self-heal) + PreToolUse before memory ops
  (`liveness.py pretool`, 60s throttle). Config = `mcp-liveness/critical.json` (basic-memory keystone,
  auto_restart:true).
- AUTO-RESTART: `mcp-liveness/restart-basic-memory.ps1` (safety-hardened: only kills a PID that owns :8765
  AND positively matches basic-memory; restarts via scheduled task `BasicMemory-HTTP-MCP` (state=Ready),
  launcher fallback `~/.basic-memory/bm-http-server.ps1`). Log: `~/.basic-memory/logs/liveness-restart.log`.
- NO DATA LOSS: `~/.claude/hooks/memory-spool/` queues failed writes + replays when back.

## Evidence this session
- restart log shows the watchdog FIRED 2x (05:08, 05:11) doing Stop+Start of the scheduled task.
- a note that failed to write while DOWN ("Reframe v1.3 post-build...") was spool-queued then replayed —
  present in recent_activity; spool now drained.
- daemon live now (pid on :8765, recent_activity responds).

## Root cause of the deaths (separate, already-tracked)
Not a basic-memory bug — the daemon gets OOM-killed under RAM pressure (harness+WSL+fleet on 32GB, see
[[ram_oom_mcp_diagnosis]]). The watchdog handles the SYMPTOM robustly; reducing death FREQUENCY = the
separate system-RAM work (WSL cap, BOINC off), not a memory-layer fix.


## ⚠️ SUPERSEDED (2026-07-07)
The "VERIFIED, no action needed" claim above held ONLY for the clean-death case. A **stuck-task deadlock** (launcher WaitForExit-on-shim pins the task "Running" on a non-binding server → every Stop+Start recovery refused with 0x800710E0) kept memory DOWN all day 2026-07-07. Real root cause + fix (force-recover + marker-based anti-thrash grace guard, PR #40) in [[basic-memory-self-heal-real-root-cause-fix-2026-07-07]]. Lesson: one happy-path "verified" ≠ verified.