# Workstation Codex MCP Bundle

Curated Windows-first MCP bundle for the canonical Codex profile at `C:\Users\Prekzursil\.codex\config.toml`. This folder preserves the exact workstation setup needed to rebuild the current Codex + VS Code + PromptBridge environment without rediscovery.

## Provenance split
- **Self-made**: `codex_consult`, `promptbridge_talk`, and the editor-local `prompt-optimizer-button`.
- **Modified local fork**: PromptBridge runtime overrides captured under `tools/mcp/agent-lanes-codex/local-overrides/` and `tools/web/agent-lanes-chatgpt-web/local-overrides/`.
- **Curated upstream picks**: Notion, GitHub, Linear, Playwright, Chrome DevTools, Figma, Sentry, SonarQube, Terraform, MindsDB, Docker, Memory, Context7, and selected optional extras.

## Key workstation decisions
- Canonical MCP source of truth: `C:\Users\Prekzursil\.codex\config.toml`
- VS Code is secondary: no duplicated raw `mcpServers` block in `settings.json`
- `chatgpt.runCodexInWindowsSubsystemForLinux = false`
- `chatgpt.openOnStartup = false`
- PromptBridge desktop autostart is disabled by default to stop constant browser / Electron noise
- Windows remains the canonical Codex home; `.codex-vscode` is migration/comparison input only
- Serena and Nuxt are no longer part of the active curated MCP set

## Current health summary
- **Verified now**: GitHub auth, Linear auth (historical proof), MindsDB local health, Context7 token persistence, Semgrep CLI availability, Prompt Optimizer local smoke test
- **Auth-gated but intentionally enabled**: Notion, Figma
- **Configured but needs repair or fresh proof**: Terraform (disabled by default until a valid token is supplied), SonarQube (token/config present but runtime not freshly proved), Notion (first-use auth), Unity/Ghidra (native handshakes required)
- **Enabled but partial by design**: `codex_consult`, `promptbridge_talk` under the hybrid-explicit lane model
- **Installed/staged but intentionally disabled**: Unity MCP, Ghidra MCP
- **Removed for noise or drift**: Serena and Netlify; Nuxt remains removed and historical only

## Files in this project
- `bundle.manifest.json`: current bundle membership and provenance split
- `config/codex-config-curated.toml`: current canonical Codex config snapshot
- `config/vscode-chatgpt-supplement.json`: VS Code settings that matter for this setup
- `env/private-env.windows.json`: plaintext private env bundle, committed by owner request
- `env/apply-private-env.ps1`: bootstrap script for rehydrating the env bundle
- `audits/2026-03-11-mcp-and-extension-audit.md`: process noise + MCP/extension audit
- `audits/2026-03-11-vscode-extension-inventory.md`: full extension classification report
- `audits/2026-03-11-vscode-extension-inventory.json`: machine-readable extension inventory
- `recommendations/apps-and-extensions.md`: suggested MCPs, Codex apps, skills, and extension cleanup candidates
- `references/upstream-sources.md`: upstream docs used for staged MCP decisions and CLI-only recommendations
- `scripts/validate-workstation-bundle.ps1`: local validation helper for this bundle
- `validation/2026-03-11-local-validation.md`: captured validation evidence
