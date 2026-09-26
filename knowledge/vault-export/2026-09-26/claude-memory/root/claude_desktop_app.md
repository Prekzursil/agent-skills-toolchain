---
name: claude-desktop-app
description: Claude DESKTOP app (≠ Claude Code CLI) — MSIX→standalone swap, config
  paths, extension/crash facts
metadata:
  node_type: memory
  type: project
  originSessionId: 02fb250a-94df-41d8-b978-bb35b7666dc0
permalink: main/claude-memory/root/claude-desktop-app
---

The **Claude Desktop** app (Chat/Cowork/Code GUI) is SEPARATE from the **Claude Code CLI** (`~/.local/bin/claude.exe` + `~/.claude.json` + the `agents` harness). User instruction: **do NOT touch the CLI/agents harness** when fixing Desktop. Its MCP servers are **Desktop Extensions** (.dxt/.mcpb), not `mcpServers` in any json.

**2026-05-24: replaced the MSIX (Microsoft Store) build with the standalone build** because MSIX caused real bugs:
- Installed read-only to `C:\Program Files\WindowsApps\Claude_...` → app spammed `EBUSY: resource busy or locked, copyfile ...` every session trying to copy its Chrome native-host binary; virtualized `%APPDATA%\Claude` into the ugly `AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\`.
- Standalone = Squirrel `Claude-Setup-x64.exe` (signed "Anthropic, PBC") from `https://storage.googleapis.com/osprey-downloads-c02f6a0d-347c-492b-a752-3e0651722e97/nest-win-x64/Claude-Setup-x64.exe`; installs to `%LOCALAPPDATA%\AnthropicClaude\app-<ver>\` (bootstrap 0.14.10 → auto-updates to current 1.8555.2, same as MSIX) + real `%APPDATA%\Claude`.

**Migration recipe (worked, login survived):** back up `LocalCache\Roaming\Claude\` (robocopy, skip Cache/GPUCache/vm_bundles), `Remove-AppxPackage Claude`, run installer, close app, robocopy backup → `%APPDATA%\Claude`. Login persists because Electron cookies are DPAPI-encrypted to the **user** (copy `Local State` + `Network\` + `Local Storage` + `IndexedDB` together). No old-package absolute paths in config, so no path rewrite needed.

**Config locations:** extensions in `%APPDATA%\Claude\Claude Extensions\<ant.dir...id>\`; registry `extensions-installations.json` = `{"extensions":{"<id>":{...}}}`. Diagnostic report (user can generate from app) lands in `Documents\claude-diagnostic-*\` (mcp-log.txt, main.log, system-info.txt, cowork-vm-log.txt).

**Broken extensions (Windows):** `ant.dir.gh.k6l3.osascript` (Control your Mac) + `ant.dir.gh.k6l3.spotify` — macOS-only (AppleScript/osascript), removed. Still failing: `ant.dir.gh.sap.mdk-mcp-server` (SAP MDK), `ant.dir.gh.cursortouch.android-mcp` (Android-MCP, wants adb), `ant.dir.gh.oogunbiyi21.stats-compass-mcp`.

**Crash cause = OOM, NOT install type** (reproduced on standalone): ~23 extensions each spawn a Node process; on launch they all download updates at once → memory spike crashes the renderer when free RAM is low (machine has 32GB but Docker+WSL+kind+agents leave it tight). Fix = fewer concurrent extensions. See [[disk_cleanup_c_drive]] for the broader RAM/load context.

**Pruning Desktop extensions STICKS (not re-synced from account — verified):** while app closed, delete dir `Claude Extensions\<id>\` + remove the `<id>` key from `extensions-installations.json` `.extensions` (reserialize with ConvertTo-Json -Depth 60) + delete stub `Claude Extensions Settings\<id>.json`. Gotcha: a `.backup-<ts>` dir's registry key is the canonical id WITHOUT the suffix — after removing, reconcile registry-vs-disk and drop orphan entries (entries with no dir → errors). 2026-05-24 pruned 29→11. KEPT: Filesystem, Windows-MCP, Desktop Commander, Figma, Docling, Kubernetes, Apify, pdf-viewer, PDF Tools (pdf-filler), Shadcn UI, ToolUniverse. `mcp-info.json` in logs is a stale cache — trust recently-written `mcp-server-*.log` for what's actually loaded.