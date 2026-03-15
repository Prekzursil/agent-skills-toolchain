# 2026-03-11 local validation

## Canonical config and settings
- `C:\Users\Prekzursil\.codex\config.toml` parses successfully with Python `tomllib`.
- Serena is no longer present in the canonical MCP config.
- Nuxt, Netlify, and Terraform are not present in the canonical MCP config.
- `ghidra` is enabled in canonical config.
- `unity` is no longer present in canonical config.
- `notion` now targets `https://mcp.notion.com/mcp`.
- `chatgpt.runCodexInWindowsSubsystemForLinux = false` remains set.
- `chatgpt.openOnStartup = false` remains set.
- `codecov.api.url` now points at `https://api.codecov.io`.
- `codecov.coverage.enabled = false` remains set to keep the extension quieter by default.
- BrowserStack plaintext values remain out of VS Code settings and persisted to user + machine env.
- VS Code server sampling no longer includes Terraform or Postgres.
- Semgrep settings point at `C:\Users\Prekzursil\.local\bin\semgrep.exe` and use quieter defaults.

## PromptBridge and Codex lanes
- PromptBridge desktop autostart remains disabled by env.
- `codex_consult` remains enabled but partial while runtime drift persists under live locks.
- `promptbridge_talk` remains enabled-manual-ready under the hybrid-explicit model.

## MCP and integration runtime checks
- MindsDB local health responds on `http://127.0.0.1:47334/mcp/status` and `/mcp/sse`.
- `codex mcp login notion` completed successfully on 2026-03-11, confirming the interactive OAuth path works with the canonical `https://mcp.notion.com/mcp` URL.
- Local Ghidra headless health responds on `http://127.0.0.1:8089/check_connection` and `/mcp/schema` using the installed D-drive toolchain.
- Unity MCP was removed completely from the active workstation bundle by owner preference, including the local `D:` staging checkout and env references.
- `D:\Tools\codecov-cli\.venv\Scripts\codecovcli.exe --help` succeeds.
- `D:\Tools\chromatic-playwright\package.json` exists with `chromatic`, `@chromatic-com/playwright`, and `playwright`, and `CHROMATIC_PROJECT_TOKEN` is now persisted locally for token-backed browser-free validation.
- `npx playwright test --reporter=line` now generates `test-results\chromatic-archives`, and `npm run chromatic:dry-run` from `D:\Tools\chromatic-playwright` completes successfully with the persisted token without any browser/site check.
- `SENTRY_HOST` is persisted in both User and Machine environment scopes as `https://sentry.io`, and a direct Sentry API request succeeds.
