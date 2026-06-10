---
name: hexstrike-ai-setup
description: Use when installing, wiring, validating, or troubleshooting the local HexStrike AI binary and runtime environment for Codex, Claude, or Gemini ; do NOT use for MCP server registration wiring (use hexstrike-ai-mcp) or running an active authorized engagement (use hexstrike-ai-authorized-engagement) ; returns a validated running HexStrike runtime.
---

# HexStrike AI Setup

## Overview
Use this skill for the local Windows-first HexStrike runtime that backs MCP access through the repo-owned `tools/mcp/hexstrike-ai/` wrapper.

## When to use
- A user wants HexStrike installed or updated locally
- A user wants HexStrike configured for Codex, Claude, or Gemini
- A HexStrike MCP registration exists but does not connect
- The localhost HexStrike API server on `127.0.0.1:8888` needs validation

## Workflow
1. Read `tools/mcp/hexstrike-ai/README.md`.
2. Run `tools/mcp/hexstrike-ai/scripts/install-hexstrike-ai.ps1` for the local upstream checkout and launcher.
3. Verify the local server with `tools/mcp/hexstrike-ai/scripts/validate-hexstrike-ai.ps1`.
4. Confirm the three client registrations all point at the same launcher path.

## Stop rules
- Keep HexStrike bound to `127.0.0.1` unless the user explicitly asks for a networked design.
- Do not claim the setup is healthy without fresh `/health`, Codex, Claude, and Gemini evidence.
- If upstream startup or protocol behavior breaks one of the clients, record the exact blocked state instead of silently downgrading the integration.
