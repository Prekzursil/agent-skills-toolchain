---
title: mcp-gui
type: note
permalink: dqverify-repo-20261013/agent-self/config/commands/mcp-gui
---

Launch the mcp-manager — a cross-plane MCP server manager (PySide6 desktop window).

Usage: /mcp-gui [--inline]   (add -Tui to launch.ps1 for the legacy Textual TUI)

Opens the mcp-manager desktop window (PySide6) which shows all MCP servers across the
Claude / Codex / mcp-funnel planes. From the TUI you can:
  - See live status (connected / error / needs-auth / pending) for each server
  - Multi-select servers and bulk enable or disable them
  - Apply a loadout (saved disable-list) or switch a funnel profile
  - Launch the external auth flow for any server that needs authentication

Run this Bash command to start it:
```bash
powershell -NoProfile -File "D:/tools/mcp-manager/launch.ps1" -Inline
```

If you want a new window instead, omit -Inline:
```bash
powershell -NoProfile -File "D:/tools/mcp-manager/launch.ps1"
```

Prerequisites: uv is installed at {{USER_HOME}}/.local/bin/uv.exe and
the venv has been created (run install.ps1 once if not).

Note: this command launches a TUI in your terminal — it cannot display inside
the Claude chat interface itself. The Bash command above will open the manager
in your current shell (with -Inline) or in a new PowerShell window.