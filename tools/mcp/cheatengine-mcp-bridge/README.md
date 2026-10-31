---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/cheatengine-mcp-bridge/readme
---

# Cheat Engine MCP Bridge

`tools/mcp/cheatengine-mcp-bridge/` is the repo-owned wrapper for the upstream Windows-only `miscusi-peek/cheatengine-mcp-bridge` project.

## Provenance
- **Curated upstream**: `miscusi-peek/cheatengine-mcp-bridge` at commit `cc7965094781209768c71a0ec3ab5dfcd20e24a2`
- **Repo-owned wrapper**: local install, autorun bootstrap, Codex MCP registration snippet, and validation helpers

## Why this exists
The upstream project is a Python MCP server plus a Cheat Engine Lua bridge. This repo does not vendor the whole project. Instead it keeps a thin, Windows-first integration layer so the workstation can install, validate, and document the bridge without taking ownership of upstream source maintenance.

## Local install shape
- upstream checkout: `C:/Users/Prekzursil/.local/opt/cheatengine-mcp-bridge`
- venv: `C:/Users/Prekzursil/.local/opt/cheatengine-mcp-bridge/.venv`
- CE autorun wrapper: `C:/Program Files/Cheat Engine/autorun/zz_ce_mcp_bridge.lua`
- Codex MCP entry: `mcp_servers.cheatengine` in the canonical `config.toml`

## Operator flow
1. Run `scripts/install-cheatengine-mcp-bridge.ps1`
2. Restart Cheat Engine so the autorun wrapper loads the Lua bridge
3. Attach Cheat Engine to the target process
4. Run `scripts/validate-cheatengine-mcp-bridge.ps1`
5. If `-RequireLivePipe` is used, confirm the bridge answers `ping`

## Stop rules
- Reinstall with Cheat Engine closed so the autorun file can be updated safely
- Treat live process writes as a separate lane from installation and read-only validation
- If the autorun log shows startup but the Python side still cannot connect to the pipe, stop and debug the bridge transport instead of pretending live analysis is working