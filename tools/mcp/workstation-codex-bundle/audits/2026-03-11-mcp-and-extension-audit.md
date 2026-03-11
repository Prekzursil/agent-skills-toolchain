# 2026-03-11 MCP and extension audit

## Process snapshot
A fresh non-destructive process snapshot still shows heavy helper-process sprawl during active Codex and VS Code use: about 96 `Code.exe`, 153 `node.exe`, 53 `uvx.exe`, 45 `msedge.exe`, and very high Docker-backed MCP churn. `docker ps` grouped output showed about 116 `ghcr.io/pgedge/postgres-mcp:latest` containers and 13 `hashicorp/terraform-mcp-server:0.4.0` containers alive during the snapshot.

## Root cause of browser and desktop noise
The biggest browser-noise fix already applied is PromptBridge Desktop autostart suppression. The remaining churn now looks more like duplicate helper processes and Docker-backed MCP container storms than browser-open-on-activation behavior.

## MCP adjustments
- Removed from active canonical config: Serena
- Removed from active canonical config earlier and cleaned from the curated bundle: Nuxt
- Enabled and verified or locally healthy: GitHub, MindsDB, Context7, Memory
- Enabled and historically proved but not freshly runtime-checked in this pass: Linear
- Enabled but auth-gated: Notion, Figma
- Enabled but repair needed: Terraform, Sentry
- Enabled but noisy and worth later runtime tuning: Docker, Postgres
- Staged-disabled: Unity, Ghidra
- Removed: Netlify

## Extension audit highlights
- Total installed extensions: 147
- Main overlap zones: extra AI assistants, duplicate GitHub Actions support, remote repo browsing overlap, DB viewer overlap, and icon theme duplication
- Highest-signal cleanup candidates are captured in `2026-03-11-vscode-extension-inventory.md`

## Semgrep
- `semgrep.semgrep@1.16.0` remains installed
- `semgrep` CLI is now installed at `C:\Users\Prekzursil\.local\bin\semgrep.exe`
- VS Code settings were tuned quieter: `semgrep.trace.server = "messages"`, `semgrep.useExperimentalLS = false`, `semgrep.scan.onlyGitDirty = true`, and `semgrep.scan.maxTargetBytes = 100000000`

## Remaining limitation
`codex_consult` and `promptbridge_talk` are still partial rather than fully green. The runtime tree remains live-locked by active Codex sessions, so a cold `orchestration:update` has not yet been completed. Current policy remains hybrid-explicit: keep lanes available, keep autostart quiet, and avoid killing active Codex to force a runtime refresh.
