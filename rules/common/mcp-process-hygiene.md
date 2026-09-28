# MCP Process Hygiene (non-negotiable)

Measured 2026-09-20: dead sessions had left **397 orphaned MCP-class processes**
(node/python/uv/uvx + zombie cmd/conhost chains) holding **115.8 GB of commit**
on a 31.6 GB-RAM box — the machine was running out of pagefile and every agent
on it stalled. Root cause: every Claude/Codex/Cursor session instantiates the
full global MCP registry (~80 servers, 1–3 processes each); sessions that die
without cleanup leave their stdio MCP chains behind, and they accumulate.

## The rules

1. **Reap before you fan out.** Before launching ANY Workflow, background
   agent, or second session: check MCP process count and free RAM.
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Prekzursil\.agents\scripts\mcp_ram_audit.ps1`
   If MCP-class count > 150 **or** free RAM < 4 GB → run the reaper first:
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Prekzursil\.agents\scripts\reap_orphan_mcp.ps1`
   (`-WhatIfOnly` to inspect first). It is SAFE by construction: it kills only
   processes whose ancestry reaches neither a live agent root (claude/code/
   cursor/codex/trae/windsurf) nor services.exe, and it whitelists the shared
   daemons (mcp-hub, basic-memory :18765, agent-mail :18812, auth2api :18317,
   actions-runner, cc-gateway, socat).
2. **Never run fleets on a full box.** Concurrent Workflow agents are capped by
   the harness, but 16 × (registry + transcripts) on this box = starvation.
   If free RAM < 8 GB, do not launch multi-agent work — reap, free, or go solo
   (extends G-26 to all agent fleets, not just `agent worker start`).
3. **One session = the whole registry.** Opening a Claude/Codex session costs
   ~60–100 MCP processes (~10–25 GB commit). Do not leave idle sessions open;
   close them when done.
4. **Never fix RAM by editing MCP configs.** Disabling/enabling servers in
   `.claude.json` / `agents.json` to "save memory" destroys load-bearing
   curation — reap orphans instead.
5. **A scheduled task (`MCPOrphanReaper`, every 30 min) auto-reaps.** If it is
   missing, re-register:
   `schtasks /Create /TN MCPOrphanReaper /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Prekzursil\.agents\scripts\reap_orphan_mcp.ps1" /SC MINUTE /MO 30 /F`

## Symptoms that mean "run the reaper"

Simple commands take minutes · agents stall with 0 completions · free RAM
< 1 GB while no single process is large · commit charge > 90 GB · zombie
`cmd.exe`/`conhost.exe` pairs in the process table.
