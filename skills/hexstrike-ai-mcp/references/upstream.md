---
title: upstream
type: note
permalink: dqverify-repo-20261013/skills/hexstrike-ai-mcp/references/upstream
---

# Upstream and Local Notes

- Upstream repo: `https://github.com/0x4m4/hexstrike-ai`
- Local install root on this workstation: `C:/Users/Prekzursil/.local/opt/hexstrike-ai`
- Upstream quick setup creates a virtual environment, installs `requirements.txt`, and runs `python3 hexstrike_server.py`.
- The upstream client snippet points clients at `hexstrike_mcp.py --server http://localhost:8888`, but Codex/Claude/Gemini on this machine already rely on a framed wrapper because the local clients expect Content-Length MCP stdio.
- Canonical repo helper commands:
  - `py -3 tools/mcp/reverse-engineering-mcp-bundle/scripts/sync_hexstrike_wrapper.py`
  - `py -3 tools/mcp/reverse-engineering-mcp-bundle/scripts/register_mcp_server.py --client codex --manifest tools/mcp/reverse-engineering-mcp-bundle/manifests/hexstrike-ai.json`