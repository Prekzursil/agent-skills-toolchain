# 2026-03-11 MCP and extension audit

## Process snapshot
A non-destructive process snapshot showed heavy helper-process sprawl during active Codex/VS Code use: roughly 90 `Code.exe`, 94 `node.exe`, 59 `uvx.exe`, 42 `msedge.exe`, 11 `codex_consult` nodes, 11 `promptbridge_talk` nodes, 16 Serena launches, and 31 `docker-mcp` helpers.

## Root cause of browser / desktop noise
The main noisy behavior came from PromptBridge Desktop auto-launch inside `ensureDesktopRunning(...)`. The workstation policy now disables autostart by default and requires explicit desktop readiness for the talk lane. This preserves Lane A usefulness and stops repeated browser/Electron opening during status or curator checks.

## Tokens and persistence
- BrowserStack secrets were moved out of VS Code settings into user + machine env.
- Empty `NETLIFY_AUTH_TOKEN` was removed.
- Context7 token was later added to user + machine env.
- The env bootstrap bundle is saved under `env/` for workstation rebuilds.

## MCP adjustments
- Enabled and verified: Serena, GitHub, Linear, MindsDB
- Enabled but auth-gated: Notion, Figma
- Enabled but auth currently failing: Terraform
- Staged-disabled: Unity, Ghidra
- Disabled: Nuxt
- Removed: Netlify

## VS Code alignment
- `chatgpt.runCodexInWindowsSubsystemForLinux = false` kept
- `chatgpt.openOnStartup = false` set
- stale WSL-only Azure Logic Apps runtime paths removed
- BrowserStack plaintext values removed from `settings.json`

## Extension audit highlights
Likely keep: `openai.chatgpt`, `github.copilot`, `github.copilot-chat`, `digitarald.agent-memory`, `ms-edgedevtools.vscode-edge-devtools`, `docker.docker`, `github.vscode-pull-request-github`, `sonarsource.sonarlint-vscode`, `dbaeumer.vscode-eslint`, `charliermarsh.ruff`, `ms-python.python`, `ms-dotnettools.csdevkit`, `ms-vscode.remote-wsl`.

Likely redundant or worth pruning if unused:
- `github.vscode-github-actions` vs `me-dutour-mathieu.vscode-github-actions` (keep one)
- `github.remotehub` + `ms-vscode.remote-repositories` if you no longer browse GitHub remotely from VS Code
- `wallabyjs.wallaby-vscode` if Wallaby is not part of the active workflow
- `firefox-devtools.vscode-firefox-debug` if Chrome DevTools + Playwright cover browser debugging needs

## Remaining limitation
`npm run orchestration:update` could not complete while the live PromptBridge runtime was locked by active Codex sessions (`EPERM` rename). Local runtime source and canonical config were patched directly and then snapshotted into this repo. A cold update can be attempted later when Codex is not actively using the runtime directory.
