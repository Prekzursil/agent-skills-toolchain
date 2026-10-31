---
title: 2026-03-29-local-validation
type: note
permalink: dqverify-repo-20261013/tools/mcp/cheatengine-mcp-bridge/validation/2026-03-29-local-validation
---

# 2026-03-29 local validation

## Completed
- Installed upstream checkout under `C:/Users/Prekzursil/.local/opt/cheatengine-mcp-bridge`
- Created venv and installed `mcp`, `pywin32`, and upstream requirements
- Installed Cheat Engine autorun wrapper at `C:/Program Files/Cheat Engine/autorun/zz_ce_mcp_bridge.lua`
- Added `mcp_servers.cheatengine` to the canonical `config.toml`
- Verified `codex mcp list` shows `cheatengine` as enabled
- Verified `scripts/validate-cheatengine-mcp-bridge.ps1 -RequireLivePipe` returns a successful `ping`

## Live read-only proof
- `evaluate_lua` opened `StarWarsG.exe`
- `get_process_info` returned process id `7500`, process name `StarWarsG.exe`, and module details
- `enum_modules` returned a populated module list for the live game process
- Read-only AOB probing is now possible through the installed bridge

## Meaning
- Installation, registration, and live pipe connectivity are working
- The current proof is intentionally read-only; write/patch workflows remain a separate risk lane