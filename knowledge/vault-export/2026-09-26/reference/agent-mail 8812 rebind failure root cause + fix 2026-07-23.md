---
title: agent-mail 8812 rebind failure root cause + fix 2026-07-23
type: reference
permalink: main/reference/agent-mail-8812-rebind-failure-root-cause-fix-2026-07-23
tags:
- agent-mail
- mcp
- supervisor
- debugging
- windows
- fix
---

# agent-mail 8812 rebind failure — root cause + fix (2026-07-23)

Symptom: MCPAgentMailSupervisor task "Running" but GET http://127.0.0.1:8812/api/health = HTTP 000; did not recover after supervisor kicks or after freeing ~5.8GB RAM.

## Root cause (two-part, NOT plain RAM)
1. **Wedged orphan children accumulated.** The server child is a chain: `.venv/Scripts/python.exe` (venv shim) -> uv-managed **CPython 3.14** base interp, which actually binds. Under the box's memory/commit pressure these children wedge during import (0 CPU, ~0.5-6MB WS, frozen 13+ min). When a supervisor process dies it ORPHANS its children; the supervisor's `Invoke-StorageRootReclaim` only kills DIFFERENT-port rogues, so same-port wedged orphans are never reaped -> they accumulate and worsen pressure. Found chains 79164->55956->101984 + more.
2. **StartupGraceSec=90s too tight.** Import-heavy app (fastapi/uvicorn/sqlalchemy/mcp/rich on py3.14) cold-starts ~8s idle but ~90-150s under pressure. Supervisor kills near-ready children at the 90s edge (agentmail_supervisor.ps1:299 `if (-not (Test-Healthy)){Stop-Child}` after Start-Child's grace), every retry hits the same wall -> non-converging crash loop. External kicks ignored because task `MultipleInstances=IgnoreNew` returns "already running" (0x800710E0).

## Ruled OUT (independent probes)
- Server code fine: binds + health 200 in <9s when spawned fresh (3 runs).
- Health check fine: Test-Healthy returns true vs live server. In PS5.1 the primary HttpClient path throws "Unable to find type HttpClientHandler" and harmlessly falls back to a working Invoke-WebRequest.
- Storage lock fine: server bound with store/server.lock present.
- Port collision: nothing held 8812 (netstat + curl exit 7 agree).

## Fix applied
- Killed all wedged orphan `mcp_agent_mail` pythons.
- `schtasks /run` -> fresh child bound in ~92s -> supervisor adopted healthy (pid 40256, socket held by uv-py child 27740).
- Raised `$StartupGraceSec` 90->240 in the LOCAL untracked `~/.local/opt/mcp_agent_mail/supervisor/agentmail_supervisor.ps1` (parse-verified). Only activates on NEXT supervisor launch; running instance still has 90s.

## Verified
health 200 x2; netstat 8812 LISTENING pid 27740; /openapi.json (v0.3.4); /mail 200.

## Owner follow-ups
- Restart supervisor at low-pressure moment to activate 240s grace (or next reboot).
- Add same-port orphan reaping at supervisor startup.
- CPU-progress-aware wedge detection (kill 0-CPU children early).
- Consider pinning venv to py3.12/3.13 instead of bleeding-edge 3.14.
- `supervisor_ps_count` self-match gotcha: inline `-Command ...match 'agentmail_supervisor'` matches its own cmdline (+1). Use `-File`.
