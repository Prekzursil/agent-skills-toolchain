---
title: RAM triage gate 2026-09-20 fail-closed verdict
type: report
permalink: main/projects/biomni-local/ram-triage-gate-2026-09-20-fail-closed-verdict
tags:
- ram-triage
- fail-closed
- mcphub-outage
- biomni
- workflow-agent
---

# RAM Triage Gate 2026-09-20 — FAIL-CLOSED verdict, measurement blocked

- [decision] **go_browser=false avail_after=UNMEASURED freed=0MB top3=UNKNOWN** — fail-closed: the gate could not measure Available MBytes, so the >=3000MB threshold cannot be certified. Do NOT start the headed Chromium (Lane A bridge :18319) on this verdict; re-run the gate when a shell exists.
- [fact] INTENDED artifact path `D:\Research\tools\biomni-local\ram-triage-2026-09-20.md` could NOT be written from the workflow agent session (no native shell/file tools; McpHub down). THIS note is the durable fallback copy — copy it to that path when a shell is available.

## Why measurement was impossible (3 signals)
1. The agent toolset (deferred-tool enumeration + ToolSearch patterns `^Bash$`, `bash|powershell|shell|execute command`, `\bBash\b|\bSh\b|\bShell\b`) contains NO native shell/file tool. Only MCP tools exist.
2. The only execution path, McpHub (`mcp__McpHub__hexstrike_ai__execute_command` / `create_file`), returned **Not connected** on 3/3 calls (2x create_file, 1x execute_command). Matches the known McpHub partial outage for agent sessions while the MAIN session sees the tools.
3. Remaining connected servers (agent-mail, basic-memory, github, firecrawl, chrome-devtools, playwright) offer no safe local exec: browser-attaching tools would SPAWN a Chromium on a possibly-45MB-free box — exactly the wedge this gate exists to prevent. Rejected on doctrine.

## Steps status
- Round-1 measurements (Available MBytes, Win32_OperatingSystem, commit bytes/limit): NOT-RUN. Ground-truth brief this morning read ~45MB available (workflow-provided, UNVERIFIED by me).
- Top consumers + protected-list classification: NOT-RUN (no Get-Process).
- Reclaim: 0 MB freed. Nothing killed — nothing could be safely identified without a process list; protected list (docker, wsl, biomni daemon, harness node/pwsh) untouched by construction.
- Round-2 re-measure: NOT-RUN (nothing reclaimed).
- Notification: SendMessage to main queued successfully with the exact PS one-liner to measure + this verdict.

## Settling experiment
Re-run this gate from a session with a shell (main session or post-McpHub-restore):
`powershell -NoProfile -Command "$c=Get-Counter '\Memory\Available MBytes','\Memory\Committed Bytes','\Memory\Commit Limit';$c.CounterSamples|Select Path,CookedValue;Get-Process|Sort WorkingSet64 -Desc|Select -First 12 Name,Id,@{n='WS_MB';e={[math]::Round($_.WorkingSet64/1MB)}}"`
go_browser=true iff Available >= 3000MB after any obviously-safe orphan reclaim (never kill: docker/Docker Desktop, wsl/wslservice, biomni daemon, powershell not self-spawned, claude/node harness).

Related: [[biomni-local]], [[mcp-estate-outage]]
