---
title: phase0_status_2026-07-20
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/phase0-status-2026-07-20
---

# Phase 0 Status Report — 20.07.2026

## Owner decisions locked
1. Orchestrator: Claude Code (Grok = symbiotic executor)
2. ChatGPT path: export-folder + stream fixtures first; **live backend-api also proven**
3. Databricks: DEFAULT / bolt-datascience only
4. Cockpit: extend wfmon
5. Code home: `~/source/agent-skills-toolchain`

## Deliverables

| # | Item | Status |
|---|---|---|
| 1 | ChatGPT fixtures normalized | **DONE** → `tools/crcp/fixtures/chatgpt_desktop/v1/` |
| 2 | Inventory + health probes | **DONE** (see below) |
| 3 | Agent-mail repair | **DONE** — root cause + continuous supervisor reinstall |
| 4 | Bus Claude↔Codex proof | **DONE** — `SUCCESS:bus_proof` |
| 5 | Auth JWT / lifecycle audit | **DONE** + deep investigation |

## Health snapshot
- Databricks DEFAULT: **green** (user costin.ionescu@bolt.eu / bolt-datascience, PAT)
- Codex CLI 0.144.6: auth_mode chatgpt, access_token **valid ~10d TTL**, id_token 1h (expired OK)
- Agent-mail :8812: **healthy** shared HTTP
- MCP process sprawl: ~800 matching procs (Claude MCP eager spawn issue confirmed; denylist placement separate work)
- basic-memory :8765: process present; `/api/health` not same shape (404)

## Agent-mail supervisor root cause
- Task was running `agentmail_supervisor.ps1 **-Once**` every 1 minute with `StopAtDurationEnd=true`
- That pattern yields **0xC000013A** (CTRL_C_EXIT) when the task engine kills the process
- Official installer uses **continuous loop** (no `-Once`)
- **Fixed:** re-registered task as continuous logon loop; health OK after recycle
- MCP ASGI can wedge under hung clients while `/api/health` stays green — recycle server if tools hang

## Bus proof
- Transport: raw JSON-RPC HTTP to `http://127.0.0.1:8812/mcp` (streamablehttp_client hangs; avoid for now)
- Agents: VioletTower (claude-orchestrator) ↔ OrangeCreek (codex-executor)
- Marker round-trip confirmed in inbox + sqlite (`sqlite_marker_msgs=2`, reply=2)
- Report: `tools/crcp/reports/bus_proof.json`

## Auth + ChatGPT live bridge (bonus from deep dive)
- access_token works on `chatgpt.com/backend-api/me` and `/conversations` and `/conversation/{id}`
- Live bridge path ready; export fixtures remain offline regression
- Refresh: proactive 8d last_refresh OR 5min-to-access-exp; reactive 401; single-use refresh_token
- Report: `tools/crcp/reports/auth_json_deep_investigation_2026-07-20.md`

## Fixture set
- Stream files: 13 on disk, progressive by size; many near-duplicates with distinct hashes
- Conversation exports: 3 files, **1 unique** content (all identical) with real text
- Schema: `tools/crcp/fixtures/chatgpt_desktop/v1/SCHEMA.md`

## Next (Phase 1 candidates)
1. Auth vault CLI (`crcp auth status`)
2. ChatGPT live bridge consumer (read-only on auth.json)
3. Keep agent-mail continuous supervisor; never reintroduce `-Once` thrash
4. wfmon extension for bus + auth health