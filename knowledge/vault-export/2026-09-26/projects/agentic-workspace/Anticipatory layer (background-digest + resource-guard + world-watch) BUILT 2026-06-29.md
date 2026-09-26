---
title: Anticipatory layer (background-digest + resource-guard + world-watch) BUILT
  2026-06-29
type: note
permalink: main/projects/agentic-workspace/anticipatory-layer-background-digest-resource-guard-world-watch-built-2026-06-29
tags:
- anticipatory-layer
- background-digest
- scheduled-tasks
- resource-guard
- world-watch
- harness
- gotcha
---

# Anticipatory layer — "background dreaming" (BUILT 2026-06-29)

The proactive-partner layer addressing never-forget + grows-with-you. Runs as Windows
SCHEDULED TASKS (NOT hooks → never touches the ~6-hook ceiling). LOG + SURFACE + PROPOSE
only; NEVER auto-acts (mirrors `scripts/mcp-drift-audit.ps1` doctrine). Every trigger an
external signal. All fail-open.

## Components (all verified)
1. **SURFACE — `~/.claude/hooks/background-digest/reader.py`** (the build-first piece).
   SessionStart "check" FOLDED INTO the dispatcher `~/.claude/hooks/_dispatch/manifest.json`
   (one check object after `open-loops/resurface`; `isolate:null`, self-contained like
   heartbeat) — NOT a 2nd settings.json hook. Reads `~/.claude/BACKGROUND-DIGEST.md`, surfaces
   oldest K "[date]..." entry lines ONCE, archives to `BACKGROUND-DIGEST.archive.log`
   (loss-proof), truncates consumed lines from a FRESH re-read (concurrency-safe). Non-`[date]`
   lines (header) preserved. 22-case test + real-dispatcher 2-run e2e (surface→truncate→silent).
2. **`~/scripts/resource-guard.ps1`** (hourly task `Resource-Guard`): samples free-RAM / C:
   used% / WORST single MCP-server duplication (full-path signature, not basename — basename
   conflated to a meaningless 302) + semgrep RAM. Appends ONE digest line on a threshold cross;
   anti-spam by crossed-signature + 12h cooldown. PROPOSE = mcp_doctor audit/reap + reclaim-c-drive.
   Tested pwsh7 + 5.1.
3. **`~/scripts/world-watch.ps1` + `world-watch.yaml`** (daily task `World-Watch`): per-watcher
   fingerprint (gh_commit/gh_release/adb_package_version/http_etag/file_hash), fires only on a
   change vs baseline; first obs = silent baseline; per-watcher fail-open. Active watchers:
   bc-app-version(adb), hexstrike/bcsfe/insta-mcp(gh_commit), tbcml(gh_release). Tested both
   interpreters.

## Tasks registered (schtasks /Create, verified via /Query /XML)
- `Resource-Guard` hourly (PT1H from 00:20), `World-Watch` daily 09:30. Both HighestAvailable.
- Deliberately point at the STABLE `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe`
  (5.1) NOT the versioned WindowsApps pwsh path → a pwsh MSIX update can't silently kill the
  producers (the very "upstream broke me" class this layer catches). Scripts verified on both.

## KEY GOTCHAS (durable)
- ⭐ **Subagent SessionStart ALSO runs the dispatcher and CONSUMES the digest.** Confirmed: a
  code-reviewer Task subagent's SessionStart fired reader.py, surfaced the resource-guard line
  INTO THE SUBAGENT's context and truncated it from the live file — the user's MAIN session
  would never see it. FIX = reader skips when `transcript_path` is under `.../subagents/` or
  basename starts with `agent-` (subagent transcripts live at
  `~/.claude/projects/<proj>/<session>/subagents/agent-<id>.jsonl`). Open-loops/resurface didn't
  hit this because it never CONSUMES; any consume-on-SessionStart hook MUST guard against subagents.
- PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM; and 5.1 mangles embedded double-quotes
  in `python -c "..."` (pwsh7 doesn't). world-watch parses YAML via `python -` (STDIN, with
  `utf-8-sig`) to dodge BOTH. Reusable pattern for YAML-in-PowerShell.
- Single-element PowerShell pipeline output unrolls to a SCALAR; `$x[0]` then returns the first
  CHARACTER. Wrap in `@(...)` (bit me in a test harness).
- Scheduled tasks can't reach in-session MCP servers → world-watch uses native gh/adb/etag, not firecrawl_monitor_*.

## Live machine state observed during build
RAM ~0.3–1.2 GB free (the documented RAM-OOM is REAL right now), C: ~97–98% used, one MCP server
(`npx-cli.js`) had 67 stuck copies / ~1.9 GB aggregate MCP RAM → resource-guard correctly flagged.

## Hardening after independent code-review (2026-06-29, same day)

A code-reviewer subagent returned FIX-FIRST with 1 HIGH + 3 MED + 3 LOW; all valid, all fixed:
- HIGH: `_archive()` swallowed errors but `main()` truncated anyway -> silent loss. FIX: `_archive`
  returns bool (+fsync); truncate ONLY if archived, else re-surface next session (dup, not loss).
- MED: resource-guard advanced anti-spam state even when the digest append FAILED -> alert muted
  12h. FIX: `Write-State` only on confirmed `$ok`.
- MED: gh_release TAG NAME is attacker-influenceable and lands verbatim in SessionStart context
  (prompt-injection). FIX: `Short()` sanitizes to `[A-Za-z0-9.\-_:]` + cap 16 (display only; state
  comparison uses raw fp). gh_commit (hex sha) was already safe.
- MED: PS5.1 `Add-Content` writes a BOM on file CREATE -> first entry invisible to `^\[` regex.
  FIX: reader `_read_lines` uses `utf-8-sig`.
- LOWs: docstring loss-proof wording; `exit 0` on both .ps1 (a trailing failed gh/adb native call
  otherwise made Task Scheduler show 0x1); dispose SHA256.

## Two HARD gotchas found by RUNNING it (static review could not see these)
1. ⭐⭐ SUBAGENT digest theft (CONFIRMED in production, before+after): the FIRST reviewer subagent's
   real SessionStart ran the dispatcher, surfaced the resource-guard line INTO THE SUBAGENT and
   truncated it from the live file. After adding `_is_subagent` (transcript_path under
   `/subagents/` or basename `agent-`), a throwaway probe subagent's SessionStart LEFT a planted
   entry intact (survived=1, archive=0). Real subagent SessionStart payloads DO carry the
   `/subagents/agent-<id>.jsonl` transcript_path -> the guard keys on it correctly.
2. ⭐ gh HANG in the HIDDEN scheduled-task context: a `gh` call stalled the hidden powershell.exe
   run for minutes while a DIRECT run took 5s; worse, schtasks defaulted ExecutionTimeLimit=PT72H
   so a hang wedges the task for days + blocks the next run. FIX: `Invoke-NativeCapture`
   (Start-Process + hard `WaitForExit(ms)` + Kill-on-timeout + known-path fallback; success keyed
   on NON-EMPTY stdout to dodge the Start-Process `-PassThru` ExitCode-null gotcha), per-call
   25s/15s; PLUS `Set-ScheduledTask -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit
   10min -MultipleInstances IgnoreNew ...)`. Note: `New-ScheduledTaskSettingsSet` param is
   `-MultipleInstances` NOT `-MultipleInstancesPolicy`.

## Final verified state
reader 28/28; resource-guard + world-watch ALL PASS on pwsh7 AND 5.1; real-dispatcher e2e (main
surfaces+consumes, subagent skips); both tasks LastResult=0x0, ExecutionTimeLimit=PT10M;
world-watch baselines primed in real state. Manifest SessionStart checks now:
[bg-registry/reconcile, memory-spool/flush_check, heartbeat, open-loops/resurface, background-digest/reader].
