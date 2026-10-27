Launch the mcp-manager — a cross-plane MCP server manager (PySide6 desktop window).

Usage: /mcp-gui [--inline]   (add -Tui to launch.ps1 for the legacy Textual TUI)

Opens the mcp-manager **desktop window (PySide6)** showing all MCP servers across the
Claude / Codex / mcp-funnel planes. From the window you can:
  - See live status (connected / error / needs-auth / pending) for each server
  - Multi-select servers and **bulk enable / disable** them, with a fuzzy filter box
  - **Apply a named preset** (core / re / chem / research / social / cloud / media / docs)
    in one click, or **Save current selection** as a new preset
  - **Paste a raw `/mcp` panel dump** to seed the inventory when a live list isn't handy
  - Launch the external auth flow for any server that needs authentication
  - (Experimental, opt-in) a fragile "Try live" macro that drives the `/mcp` TUI

Config edits apply to the **current project** and take effect the **NEXT session**
