---
name: binary-ninja-mcp
description: Use when installing or configuring Binary Ninja MCP, especially when a Binary Ninja plugin or npm-based MCP bridge must be wired into Codex, Claude Code, or Gemini CLI.
---

# Binary Ninja MCP

## Overview

Use this skill for the Binary Ninja MCP workflow. Treat the host app and plugin as prerequisites; the MCP bridge alone is not enough if Binary Ninja is absent.

## Quick Workflow

1. Confirm Binary Ninja is installed. If it is missing, stop and report a host-app block.
2. Install the Binary Ninja MCP plugin through the Plugin Manager when possible; manual plugin copy is the fallback.
3. Prefer the upstream npm bridge (`npx -y binary-ninja-mcp`) for client registration.
4. Register the manifest or let the plugin auto-setup supported clients, then restart both Binary Ninja and the MCP client.
5. Switch to the plain `binary-ninja` skill when the task is about IL reasoning, scripting, or plugin development rather than MCP setup.

## Common Mistakes

- Registering the bridge before the Binary Ninja plugin exists.
- Assuming npm bridge setup replaces the Binary Ninja-side plugin requirement.
- Forgetting to restart the host app after plugin installation.

## Reference Map

Read `references/upstream.md` before choosing between plugin-manager, manual, or npm-bridge setup.
