# Workstation Codex MCP Bundle

Curated Windows-first workstation bundle for the canonical Codex profile at `C:\Users\Prekzursil\.codex\config.toml`. This folder preserves the exact MCP, editor, env, and lane setup needed to rebuild the current Codex + VS Code + PromptBridge environment without rediscovery.

## Provenance split
- **Self-made**: `codex_consult`, which now exposes both codex_* orchestration tools and promptbridge_* / agentify_* talk tools from one managed server.
- **Modified local fork**: PromptBridge runtime overrides captured under `tools/mcp/agent-lanes-codex/local-overrides/` and `tools/web/agent-lanes-chatgpt-web/local-overrides/`.
- **Curated upstream picks**: GitHub, GitHub CLI, Notion, Linear, Playwright, Chrome DevTools, Figma, Sentry, SonarQube, Semgrep, Docker, Memory, Context7, PostgreSQL, and selected optional extras including the upstream Cheat Engine bridge wrapper.
- **Curated upstream picks**: GitHub, GitHub CLI, Notion, Linear, Playwright, Chrome DevTools, Figma, Sentry, SonarQube, Semgrep, Docker, Memory, Context7, PostgreSQL, DigitalOcean MCP, and selected optional extras including the upstream Cheat Engine bridge wrapper.
- **Curated upstream local orchestration**: Ralph Orchestrator is now installed through a WSL-backed local binary plus MCP server registration, with mirrored skills shipped from this repo.
- **Curated upstream MCP config**: DigitalOcean MCP is wired through `npx @digitalocean/mcp --services apps` with env-only `DIGITALOCEAN_API_TOKEN` handling; live connectivity is intentionally env-gated until the token exists locally.
- **Curated community MCP picks**: Codecov is promoted into the active MCP bundle via `@egulatee/mcp-codecov`.
- **Curated non-MCP integrations**: Chromatic remains intentionally outside the MCP set; Qlty stays on CLI + provider workflows, and DeepScan stays on VS Code + provider workflows.

## Key workstation decisions
- Canonical MCP source of truth: `C:\Users\Prekzursil\.codex\config.toml`
- VS Code is secondary: no duplicated raw `mcpServers` block in `settings.json`
- `chatgpt.runCodexInWindowsSubsystemForLinux = false`
- `chatgpt.openOnStartup = false`
- PromptBridge desktop autostart is disabled by default to stop constant browser and Electron noise
- Windows remains the canonical Codex home; `.codex-vscode` is migration/comparison input only
- Serena, Nuxt, Netlify, Terraform, MindsDB, Ghidra, and desktop-commander are not part of the current canonical config-owned MCP bundle
- Stage 1 in this repo is workstation-only: project-specific web UI setup for Momentstudio, Webcoder, and Reframe is intentionally deferred

## Current health summary
- **Verified now**: GitHub auth, Notion OAuth login, Context7 token persistence, Sentry API reachability, Codecov community MCP startup with token + base URL, SonarQube Cloud MCP startup, Semgrep MCP wrapper startup, DeepSource MCP handshake through a local Windows wrapper, Cheat Engine local install plus live read-only SWFOC analysis, and Codex registration
- **Verified now**: Ralph Orchestrator CLI install, `ralph doctor`, and user-level MCP registration for Codex, Claude, and Gemini
- **Enabled but conservatively described**: Figma (auth-gated), SonarQube (configured against SonarQube Cloud), Semgrep (no cloud token provided in this stage), and Cheat Engine (installed locally with successful pipe ping and read-only game analysis; treat writes as a separate risk lane)
- **Enabled and verified**: `codex_consult` under the single-managed-server lane model; live `status`, `probe`, and `self-test` all returned `ok: true` on 2026-03-15
- **Removed from the active workstation bundle**: Unity MCP was removed completely by owner preference, including local `D:` staging and env references
- **Community-risk decision**: DeepSource is now enabled via a local Node wrapper because the available `deepsource-mcp-server` package is deprecated and its published main entrypoint does not start correctly on Windows without an explicit wrapper; Qlty and DeepScan remain intentionally outside MCP because the current supported workstation flows are non-MCP
- **Non-MCP integrations**: the Codecov CLI on `D:` remains available for pre-push analysis; Chromatic uses a CLI + Playwright workspace on `D:` with `CHROMATIC_PROJECT_TOKEN` persisted locally; Qlty remains a CLI/provider workflow; and DeepScan remains a VS Code supplement/provider workflow

## 2026-03-30 cross-CLI parity snapshot

- `C:\Users\Prekzursil\.local\bin` and `C:\Users\Prekzursil\AppData\Roaming\npm` are now part of the persistent user PATH so `uv`, `uvx`, `claude`, `bd`, `codex`, and `gemini` resolve from fresh shells instead of only from a primed process PATH.
- BEADS is installed locally at `C:\Users\Prekzursil\.local\bin\bd.exe` and is treated as a shared prerequisite for metaswarm, Codex, Claude, and Gemini workflows.
- Codex now uses the same full-permission baseline as the local workstation execution lane: `approval_policy = "never"` and `sandbox_mode = "danger-full-access"` in the canonical config snapshot.
- Claude already runs in the expected bypass-permissions posture; Gemini now mirrors the same no-prompt intent through a local `gemini` wrapper in `C:\Users\Prekzursil\.local\bin\`, a permissive `~/.gemini/policies/999-local-full-access.toml`, and trusted-root settings without changing `.metaswarm`.
- Superpowers is aligned across the three CLIs at upstream `v5.0.6`: Claude via the installed plugin cache, Codex via `C:\Users\Prekzursil\.codex\superpowers` plus the `C:\Users\Prekzursil\.agents\skills\superpowers` junction, and Gemini via the official extension install from `https://github.com/obra/superpowers.git`.
- Gemini now carries the shared portable skill surface from its superpowers extension plus the user-level `.agents\skills` alias; keep Codex-proprietary skills such as `codex_consult` out of the shared tier.
- The essential shared MCP baseline is currently GitHub, Codacy, DeepSource, Codecov, and the Chrome DevTools extension on Gemini, with Semgrep and SonarQube still configured but requiring extra runtime proof on Gemini before they should be described as fully healthy.

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
- `references/upstream-sources.md`: upstream docs used for staged MCP decisions, blocked-provider notes, and CLI fallback recommendations
- `scripts/validate-workstation-bundle.ps1`: local validation helper for this bundle
- `scripts/deepsource-mcp-wrapper.mjs`: repo-owned source for the Windows DeepSource wrapper that is installed under `C:\Users\Prekzursil\.local\opt\deepsource-mcp-server\`
- `validation/2026-03-11-local-validation.md`: captured validation evidence
- `audits/2026-03-30-cross-cli-parity.md`: Codex, Claude, and Gemini parity snapshot after BEADS, PATH, superpowers, and shared-MCP alignment
- `../cheatengine-mcp-bridge/validation/2026-03-29-local-validation.md`: Cheat Engine bridge install and connectivity evidence

## Config-owned vs plugin-provided MCPs

- `config/codex-config-curated.toml` tracks the canonical config-owned MCP servers.
- `codex mcp list` can also show plugin/app-provided MCP surfaces such as `cloudflare-api`, `stripe`, `supabase`, `vercel`, and `hf-mcp-server`.
- Those plugin-provided surfaces should be documented as environment facts, not mirrored into the curated config-owned bundle manifest unless they become repo-owned decisions.
