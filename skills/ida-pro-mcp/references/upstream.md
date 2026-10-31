---
title: upstream
type: note
permalink: dqverify-repo-20261013/skills/ida-pro-mcp/references/upstream
---

# Upstream Notes

- Upstream repo: `https://github.com/mrexodia/ida-pro-mcp`
- Upstream install flow:
  - `pip install https://github.com/mrexodia/ida-pro-mcp/archive/refs/heads/main.zip`
  - `ida-pro-mcp --install`
- Upstream clients explicitly mentioned by the project: Claude, Claude Code, Codex, Cursor, Gemini CLI, and others.
- Recommended local package path when automating from this repo: `C:/Users/Prekzursil/.local/opt/ida-pro-mcp/.venv`
- Windows-first stdio config should use the dedicated venv Python plus `Lib/site-packages/ida_pro_mcp/server.py`, which matches the upstream `ida-pro-mcp --config` output.
- On Windows-first setups, prefer publishing an `ida64.cmd` shim in `C:/Users/Prekzursil/.local/bin` when the installed launcher is really `ida.exe`.
- Do not claim local enablement unless IDA Pro is actually present and the plugin has been installed.