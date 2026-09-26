---
title: 'MCP config drift: basic-memory + codex absent, re-add'
type: reference
permalink: main/reference/mcp-config-drift-basic-memory-codex-absent-re-add
tags:
- mcp
- basic-memory
- codex
- config-drift
---

# MCP config drift: basic-memory + codex absent from active config (2026-07-17)

**valid_as_of: 2026-07-17.**

Symptom: `basic-memory` (+ `codex`, `ocr`) documented as mounted in CLAUDE.md but **ABSENT from the active MCP config** — `claude mcp list` showed only `[angr, cloud-hub, social-hub, figma, playwright, schrodinger]` (same 6 in BOTH `.mcp.json` project scope and `~/.claude.json` user scope). Those names appeared only as stray refs in `~/.claude/settings.json` (permissions/hooks), which does NOT mount a server. Cause: the mcp-funnel dedup / parity-rebuild consolidated the fleet and dropped them. 26 OTHER MCPs (21 claude.ai connectors + cloud-hub/social-hub/figma/playwright/schrodinger) were fine — it was specifically the local custom trio.

## Re-add (user scope)
- `claude mcp add --scope user basic-memory -- basic-memory mcp`  (attaches `~/.basic-memory/config.json` default_project `main` → `D:\basic-memory`; `basic-memory` 0.22.1 at `~/.local/bin`)
- `claude mcp add --scope user codex -- codex mcp-server`  (codex-cli 0.144.5)
Both verified `✔ Connected`. **The new tools became available SAME-SESSION** (the harness surfaced `mcp__basic-memory__*` / `mcp__codex__*` as deferred tools via ToolSearch — no restart needed, correcting the common "restart required" assumption for `claude mcp add`).

Also down at the time: `angr` (:8760 SSE ✘), agent-mail (:8812 no response). cloud-hub/social-hub connected but missing env tokens (KAGGLE/GCP/MODAL, FB).

Relates to [[Cross-AI Tools Unification]].