---
name: ida-pro-mcp
description: Use when installing or configuring mrexodia/ida-pro-mcp for IDA Pro,
  or when wiring its client config into Codex, Claude Code, or Gemini CLI after the
  IDA plugin is available.
permalink: dqverify-repo-20261013/skills/ida-pro-mcp/skill
---

# IDA Pro MCP

## Overview

Use this skill for the `mrexodia/ida-pro-mcp` workflow. The package install is lightweight, but the MCP server is only useful after IDA Pro is present and the plugin bootstrap has completed.

## Quick Workflow

1. Confirm IDA Pro is installed and launchable on the target machine. If it is missing, stop and report the setup as blocked.
2. Install or update the package in a dedicated environment. Prefer a stable path such as `~/.local/opt/ida-pro-mcp/.venv`.
3. Run `ida-pro-mcp --install` so the IDA plugin and client glue land correctly.
4. Use `ida-pro-mcp --config` or the repo manifest to register the server in Codex, Claude Code, or Gemini CLI.
5. Restart both IDA and the MCP client before verification.

## Common Mistakes

- Registering the MCP client before `ida-pro-mcp --install` has finished.
- Forgetting that IDA and some MCP clients stay resident in the background until fully quit.
- Treating package installation as success when the actual IDA-side plugin never loaded.

## Reference Map

Read `references/upstream.md` before changing client config.