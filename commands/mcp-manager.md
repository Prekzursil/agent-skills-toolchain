---
title: mcp-manager
type: note
permalink: dqverify-repo-20261013/commands/mcp-manager
---

Launch the mcp-manager — the cross-plane MCP server manager.

Usage: /mcp-manager [--inline]

Opens the PySide6 desktop manager showing MCP servers across the Claude, Codex,
and mcp-funnel planes. From the window you can:
- See live status (connected / error / needs-auth / pending) for each server.
- Multi-select servers and bulk enable or disable them.
- Apply a named preset (core / re / chem / research / social / cloud / media / docs).
- Save the current selection as a preset.
- Paste a raw `/mcp` panel dump to seed inventory.
- Launch an external authentication flow when a server needs one.
- Opt into the fragile, best-effort live-control macro only after reviewing its
  dry-run plan; wrong-window focus can toggle unintended controls.

Configuration changes apply to the current project and normally take effect in
the next host session. The manager must report when a restart/relaunch is
required; it must not claim an unverified live reconnect.

Safety boundaries:
- Claude presets write only the active project's `disabledMcpServers`; they never
  replace user-scope `mcpServers`.
- Cursor presets use the official `cursor-agent mcp enable/disable` approval
  surface. Definition attachment is a separate guarded control-plane operation.
- Every mutation is previewed and explicitly applied; failures retain rollback evidence.

CLI equivalents in `D:/tools/mcp-manager`:
`uv run app.py use <preset>` · `preset list|apply|save|delete` · `parse-list` · `status`.

Launch inline:
```powershell
powershell -NoProfile -File "D:/tools/mcp-manager/launch.ps1" -Inline
```

Launch in a new window:
```powershell
powershell -NoProfile -File "D:/tools/mcp-manager/launch.ps1"
```

Prerequisites: `uv` on `PATH` and the mcp-manager environment initialized by
`install.ps1`. Treat `D:/tools/mcp-manager/launch.ps1` as owner-controlled code
and verify its reviewed source before launch.