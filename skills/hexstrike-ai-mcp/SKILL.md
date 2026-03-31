---
name: hexstrike-ai-mcp
description: Use when installing, repairing, or registering HexStrike AI as an MCP server for Codex, Claude Code, or Gemini CLI, especially when a localhost HexStrike server needs a framed stdio bridge.
---

# HexStrike AI MCP

## Overview

Use HexStrike AI through a localhost HTTP server plus a framed stdio bridge. Preserve the local install root at `~/.local/opt/hexstrike-ai` and treat the repo bundle as the canonical source for the launcher and client manifests.

## Quick Workflow

1. Confirm the local install root exists and contains `hexstrike_server.py`, `hexstrike_mcp.py`, and a populated `.venv`.
2. Sync the canonical wrapper from `tools/mcp/reverse-engineering-mcp-bundle/wrappers/hexstrike_mcp_launcher.py` into the install root with `scripts/sync_hexstrike_wrapper.py`.
3. Verify the server answers `http://127.0.0.1:8888/health`; if not, fix the server first instead of editing MCP client configs.
4. Register `manifests/hexstrike-ai.json` into Codex, Claude, or Gemini with `scripts/register_mcp_server.py` only when the local server is healthy.
5. Restart the MCP client after any config change.

## Common Mistakes

- Registering the client before the localhost HexStrike server can answer `/health`.
- Pointing clients at the upstream `hexstrike_mcp.py` directly instead of the framed launcher.
- Moving the install root without updating `HEXSTRIKE_INSTALL_ROOT` or re-syncing the wrapper.

## Reference Map

Read `references/upstream.md` for the upstream install flow and the exact local bridge assumptions.
