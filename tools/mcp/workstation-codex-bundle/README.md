# Workstation Codex MCP Bundle

Curated Windows-first MCP bundle for the canonical Codex profile at `C:\Users\Prekzursil\.codex\config.toml`. This folder preserves the exact workstation setup needed to rebuild the current Codex + VS Code + PromptBridge environment without rediscovery.

## Provenance split
- **Self-made**: `codex_consult`, `promptbridge_talk`, and the editor-local `prompt-optimizer-button`.
- **Modified local fork**: PromptBridge runtime overrides captured under `tools/mcp/agent-lanes-codex/local-overrides/` and `tools/web/agent-lanes-chatgpt-web/local-overrides/`.
- **Curated upstream picks**: Serena, Notion, GitHub, Linear, Playwright, Chrome DevTools, Figma, Sentry, SonarQube, Terraform, MindsDB, Docker, Memory, Context7, and selected optional extras.

## Key workstation decisions
- Canonical MCP source of truth: `C:\Users\Prekzursil\.codex\config.toml`
- VS Code is secondary: no duplicated raw `mcpServers` block in `settings.json`
- `chatgpt.runCodexInWindowsSubsystemForLinux = false`
- `chatgpt.openOnStartup = false`
- PromptBridge desktop autostart is disabled by default to stop constant browser / Electron noise
- Windows remains the canonical Codex home; `.codex-vscode` is migration/comparison input only

## Current health summary
- **Verified now**: Serena visibility, GitHub auth, Linear auth, MindsDB local health, Ghidra bridge help, Unity bridge help, Prompt Optimizer local smoke test
- **Auth-gated but intentionally enabled**: Notion, Figma
- **Configured but requires fresh credential check**: Terraform (`unauthorized` with current token)
- **Installed/staged but intentionally disabled**: Unity MCP, Ghidra MCP
- **Disabled/removed for noise reduction**: Nuxt (broken DNS), Netlify (removed)

## Files in this project
- `bundle.manifest.json`: current bundle membership and provenance split
- `config/codex-config-curated.toml`: current canonical Codex config snapshot
- `config/vscode-chatgpt-supplement.json`: VS Code settings that matter for this setup
- `env/private-env.windows.json`: plaintext private env bundle, committed by owner request
- `env/apply-private-env.ps1`: bootstrap script for rehydrating the env bundle
- `audits/2026-03-11-mcp-and-extension-audit.md`: process noise + MCP/extension audit
- `recommendations/apps-and-extensions.md`: suggested MCPs, Codex apps, skills, and extension cleanup candidates
- `scripts/validate-workstation-bundle.ps1`: local validation helper for this bundle
- `validation/2026-03-11-local-validation.md`: captured validation evidence
