---
title: 2026-03-30-local-validation
type: note
permalink: dqverify-repo-20261013/tools/mcp/hexstrike-ai/validation/2026-03-30-local-validation
---

# 2026-03-30 local validation

## Completed
- Installed upstream checkout under `C:/Users/Prekzursil/.local/opt/hexstrike-ai`
- Pinned local checkout to upstream commit `83337796dcfb8cfbf733bd24d0b2c7e4f0732790`
- Created a local Python 3.11 venv and installed upstream `requirements.txt`
- Copied the repo-owned launcher to `C:/Users/Prekzursil/.local/opt/hexstrike-ai/hexstrike_mcp_launcher.py`
- Added `mcp_servers."hexstrike-ai"` to `C:/Users/Prekzursil/.codex/config.toml`
- Added a user-scoped Claude MCP registration for `hexstrike-ai`
- Added a Gemini MCP registration for `hexstrike-ai`
- Verified the localhost server returns `status = healthy` on `http://127.0.0.1:8888/health`

## Current evidence
- `codex mcp get hexstrike-ai` shows the expected local Python command and launcher path.
- `claude mcp get hexstrike-ai` shows the user-scoped registration but still reports `Status: Failed to connect`.
- `gemini mcp list` shows `hexstrike-ai` registered with the same launcher path but still reports `Disconnected`.
- The repo-owned launcher now bridges HexStrike's line-delimited upstream MCP output into framed stdio, but Claude and Gemini still need further compatibility work before they can be described as healthy.

## Meaning
- The local HexStrike runtime and localhost API are installed and usable.
- Codex, Claude, and Gemini now share the same local launcher path.
- Cross-client registration is complete, but cross-client connection proof is still partial because Claude and Gemini health checks are not yet green.