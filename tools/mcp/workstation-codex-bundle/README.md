# Workstation Codex MCP Bundle

Curated Windows-first workstation bundle for the canonical Codex profile at `C:\Users\Prekzursil\.codex\config.toml`. This folder preserves the exact MCP, editor, env, and lane setup needed to rebuild the current Codex + VS Code + PromptBridge environment without rediscovery.

## Provenance split
- **Self-made**: `codex_consult`, which now exposes both codex_* orchestration tools and promptbridge_* / agentify_* talk tools from one managed server.
- **Modified local fork**: PromptBridge runtime overrides captured under `tools/mcp/agent-lanes-codex/local-overrides/` and `tools/web/agent-lanes-chatgpt-web/local-overrides/`.
- **Curated upstream picks**: GitHub, Notion, Linear, Playwright, Chrome DevTools, Figma, Sentry, SonarQube, MindsDB, Docker, Memory, Context7, and selected optional extras.
- **Curated non-MCP integrations**: Codecov and Chromatic, both intentionally tracked outside the MCP set.

## Key workstation decisions
- Canonical MCP source of truth: `C:\Users\Prekzursil\.codex\config.toml`
- VS Code is secondary: no duplicated raw `mcpServers` block in `settings.json`
- `chatgpt.runCodexInWindowsSubsystemForLinux = false`
- `chatgpt.openOnStartup = false`
- PromptBridge desktop autostart is disabled by default to stop constant browser and Electron noise
- Windows remains the canonical Codex home; `.codex-vscode` is migration/comparison input only
- Serena, Nuxt, Netlify, and Terraform are no longer part of the active curated MCP bundle

## Current health summary
- **Verified now**: GitHub auth, Notion OAuth login, Ghidra headless health on 127.0.0.1:8089, MindsDB local health, Context7 token persistence, Sentry API reachability, Codecov local CLI
- **Enabled but conservatively described**: Figma (auth-gated), SonarQube (configured, no fresh runtime proof in this pass)
- **Enabled with native-app or headless runtime**: Ghidra is enabled in canonical config and now has a verified local headless bridge at 127.0.0.1:8089; the GUI plugin path remains optional when CodeBrowser is open
- **Enabled and verified**: `codex_consult` under the single-managed-server lane model; live `status`, `probe`, and `self-test` all returned `ok: true` on 2026-03-15
- **Removed from the active workstation bundle**: Unity MCP was removed completely by owner preference, including local `D:` staging and env references
- **Non-MCP integrations**: Codecov uses the hosted API plus a local CLI on `D:`; Chromatic uses a CLI + Playwright workspace on `D:` with `CHROMATIC_PROJECT_TOKEN` persisted locally, and local `chromatic --playwright --dry-run` now completes successfully without any browser/site auth check after aligning Playwright output to `test-results`

## Files in this project
- `bundle.manifest.json`: current bundle membership and provenance split
- `config/codex-config-curated.toml`: current canonical Codex config snapshot
- `config/vscode-chatgpt-supplement.json`: VS Code settings that matter for this setup
- `env/private-env.windows.json`: plaintext private env bundle, committed by owner request
- `env/apply-private-env.ps1`: bootstrap script for rehydrating the env bundle
- `audits/2026-03-11-mcp-and-extension-audit.md`: process noise plus MCP and extension audit
- `audits/2026-03-11-mcp-matrix.md`: server-by-server runtime stance
- `audits/2026-03-11-vscode-extension-inventory.md`: full extension classification report
- `audits/2026-03-11-vscode-extension-inventory.json`: machine-readable extension inventory
- `recommendations/apps-and-extensions.md`: suggested MCPs, Codex apps, CLI integrations, and extension cleanup candidates
- `references/upstream-sources.md`: upstream docs used for staged MCP decisions and CLI-only recommendations
- `scripts/validate-workstation-bundle.ps1`: local validation helper for this bundle
- `scripts/start-ghidra-headless.ps1`: local helper to launch the verified headless bridge on `127.0.0.1:8089`
- `validation/2026-03-11-local-validation.md`: captured validation evidence
