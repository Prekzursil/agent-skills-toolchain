# 2026-03-11 local validation

## Canonical config and settings
- `C:\Users\Prekzursil\.codex\config.toml` parses successfully with Python `tomllib`.
- Serena is no longer present in the canonical MCP config.
- Nuxt, Netlify, and Terraform are not present in the canonical MCP config.
- `ghidra` is enabled in canonical config.
- `unity` remains disabled in canonical config.
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
- Notion remains enabled and OAuth-backed; this pass keeps runtime proof conservative/auth-gated rather than claiming a fresh post-login success.
- Ghidra is enabled in canonical config; prior local bridge health succeeded when the plugin/server was running. The current bridge still depends on the Ghidra app/plugin being open.
- Unity bridge help remains available through `uvx`, but no local Unity Editor/project handshake was available in this pass.
- `D:\Tools\codecov-cli\.venv\Scripts\codecovcli.exe --help` succeeds.
- `D:\Tools\chromatic-playwright\package.json` exists with `chromatic`, `@chromatic-com/playwright`, and `playwright`, but `CHROMATIC_PROJECT_TOKEN` is still missing.
- `SENTRY_HOST` is persisted in both User and Machine environment scopes as `https://sentry.io`, and a direct Sentry API request succeeds.

## Prompt Optimizer
- `node --check tools/editor/prompt-optimizer-button/extension.js` passes.
- `node tools/editor/prompt-optimizer-button/scripts/smoke-test.js` passes.
- Installed Prompt Optimizer remains `prekzursil-local.prompt-optimizer-button@0.1.0`.
