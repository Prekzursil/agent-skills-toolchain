---
name: ghidra-mcp
description: Use when installing or configuring GhidraMCP for a local Ghidra workflow, or when bridging its MCP client into Codex, Claude Code, or Gemini CLI after the Ghidra extension is installed.
---

# Ghidra MCP

## Overview

Use this skill for the LaurieWired `GhidraMCP` workflow. The MCP client side is simple, but it depends on a Ghidra extension and a reachable local Ghidra HTTP server.

## Quick Workflow

1. Confirm Ghidra is installed. If the host app is missing, stop and report a host-app block.
2. Install the `GhidraMCP` extension from the upstream release ZIP and restart Ghidra.
3. Confirm the Ghidra-side HTTP server is enabled and note the port (default `127.0.0.1:8080`).
4. Locate the bridge script (`bridge_mcp_ghidra.py`) and pass its absolute path through the repo manifest placeholder.
5. Register the resolved manifest into Codex, Claude Code, or Gemini CLI.

## Common Mistakes

- Forgetting to install the Ghidra extension before editing client config.
- Using the wrong bridge path or the wrong HTTP server port.
- Claiming success without checking that the Ghidra-side HTTP server is actually listening.

## Reference Map

Read `references/upstream.md` for the exact upstream JSON snippet and placeholder details.
