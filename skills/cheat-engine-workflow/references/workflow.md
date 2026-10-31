---
title: workflow
type: note
permalink: dqverify-repo-20261013/skills/cheat-engine-workflow/references/workflow
---

# Cheat Engine Workflow Notes

## Local support

- Codex MCP server name: `cheatengine`
- Local bridge path: `%USERPROFILE%\.local\opt\cheatengine-mcp-bridge\MCP_Server\mcp_cheatengine.py`

## Best use cases

- Value scans and rescans
- Pointer sanity checks
- AOB confirmation for suspected functions or code caves
- Structure discovery that needs quick runtime feedback

## Escalation rules

- Use `$x64dbg` when you need call flow, branch logic, or breakpoint-led reasoning.
- Use `$dump-to-signature-workflow` when a Cheat Engine discovery needs to become a durable pattern.