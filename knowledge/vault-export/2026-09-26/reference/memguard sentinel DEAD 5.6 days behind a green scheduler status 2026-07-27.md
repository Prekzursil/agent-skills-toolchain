---
title: memguard sentinel DEAD 5.6 days behind a green scheduler status 2026-07-27
type: note
permalink: main/reference/memguard-sentinel-dead-5.6-days-behind-a-green-scheduler-status-2026-07-27
tags:
- memguard
- harness
- gotcha
- urgent
- '2026-07-27'
---

**valid_as_of: 2026-07-27 11:04.** Found by `monitorcore.health_source`'s dead-man rule the
moment it was deployed (PR #240) — the module's first live poll caught it.

## The finding
`~/.claude/system-health/events.ndjson` has not been appended to since **2026-07-21 20:57**
(198 lines, 126,263 bytes, last sample ts `2026-07-21T17:57:55Z`). That is **5.6 days blind**.

## Why nobody noticed: a GREEN scheduler status masking a dead feed
```
MemGuardCommitWatchdog   State=Running
  LastRunTime    27-Jul-26 11:02:51      <- 2 minutes before the check
  NextRunTime    27-Jul-26 11:06:18      <- firing every ~3.5 min
  LastTaskResult 267009                  <- 0x41301 "currently running", a NORMAL code
```
Every signal a human would check says healthy. The task genuinely fires; it just is not producing
samples. Writer is `~/.local/opt/memguard/sentinel.ps1` (10,789 bytes, **mtime Jul 21** — the same
day the feed stopped, so a Jul-21 edit is the prime suspect).

## Why it matters
memguard is the guard against the **commit-exhaustion box-freeze**
([[reference_commit_exhaustion_root_cause_2026-07-19]]) — the box freezes on COMMIT via
RAM+pagefile (Event 2004), NOT on RAM OOM, and Task Manager hides it. That protection has been
unobserved since Jul 21.

## The generalisable lesson
**Task-scheduler state is a single signal, and it measures the LAUNCHER, not the WORK.** "Running
+ recent LastRunTime + a non-error result" is fully compatible with producing nothing. The only
honest liveness test for a producer is its OUTPUT growing — which is exactly the dead-man rule
`health_source` implements: *a readable file is not a live feed; a sample older than `dead_man_s`
is STALLED, not a green row.* Pairs with [[main/reference/single-signal-verification]].

Tracked as open loop `7294e3f9`. DIAGNOSE: run `sentinel.ps1` by hand and read its error; check
whether the Jul-21 edit introduced a fault; confirm it can still append to the events file.
