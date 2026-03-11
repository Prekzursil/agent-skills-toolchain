# 2026-03-11 local validation

## Canonical config and settings
- `C:\Users\Prekzursil\.codex\config.toml` parses successfully with Python `tomllib`.
- `chatgpt.runCodexInWindowsSubsystemForLinux = false` remains set.
- `chatgpt.openOnStartup = false` is now set.
- BrowserStack plaintext values were removed from VS Code settings and persisted to user + machine env.
- stale WSL-only `azureLogicAppsStandard.*` path settings were removed.

## PromptBridge / Codex lanes
- Local runtime patches were applied to:
  - `mcp-lib.mjs` (desktop autostart disabled by env)
  - `codex-orchestration.mjs` (structured `fallback_to_lane_a` when curation is unavailable)
  - `bootstrap.mjs` (managed config block now includes the autostart-disabled env vars)
- `npm run orchestration:status -- --json` sees both managed servers with `PROMPTBRIDGE_DESKTOP_AUTOSTART = false`.
- `npm run orchestration:probe -- --json` still reports bootstrap drift because the runtime directory was live-locked and `orchestration:update` could not rename the runtime tree.
- `npm run orchestration:self-test -- --json` confirmed tool visibility but the talk lane remained manual-ready rather than auto-started, which is the intended no-noise policy.

## MCP runtime checks
- Serena tool visibility proved by a live `get_current_config` call.
- GitHub auth proved by a live `get_me` call.
- Linear auth proved by a live `list_teams` call.
- MindsDB health proved by `GET http://127.0.0.1:47334/mcp/status -> 200` and `/mcp/sse -> 200 text/event-stream`.
- Notion first-use auth gate proved by `GET https://mcp.notion.com/sse -> 401 invalid_token`.
- Terraform container help worked, but the live Terraform MCP call returned `unauthorized`; token repair is still needed.
- Ghidra bridge help worked from `D:`.
- Unity stdio bridge help worked from `uvx`.

## Prompt Optimizer Button
- `node --check tools/editor/prompt-optimizer-button/extension.js` passed.
- `node tools/editor/prompt-optimizer-button/scripts/smoke-test.js` passed.
- The installed VS Code extension remains `prekzursil-local.prompt-optimizer-button@0.1.0`.
