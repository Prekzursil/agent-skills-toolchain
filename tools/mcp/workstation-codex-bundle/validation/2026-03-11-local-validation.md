# 2026-03-11 local validation

## Canonical config and settings
- `C:\Users\Prekzursil\.codex\config.toml` parses successfully with Python `tomllib`.
- Serena is no longer present in the canonical MCP config.
- Nuxt is not present in the canonical MCP config.
- `linear` and `pdf-reader` now have explicit `enabled = true` values.
- `chatgpt.runCodexInWindowsSubsystemForLinux = false` remains set.
- `chatgpt.openOnStartup = false` remains set.
- BrowserStack plaintext values remain out of VS Code settings and persisted to user + machine env.
- VS Code server sampling no longer includes Serena.
- Semgrep settings now point at `C:\Users\Prekzursil\.local\bin\semgrep.exe` and use quieter defaults.

## PromptBridge and Codex lanes
- PromptBridge desktop autostart remains disabled by env.
- `codex_consult` remains enabled but partial while runtime drift persists under live locks.
- `promptbridge_talk` remains enabled-manual-ready under the hybrid-explicit model.

## MCP runtime checks
- MindsDB local health still responds on `http://127.0.0.1:47334/mcp/status` and `/mcp/sse`.
- Notion still presents the expected first-use auth gate at `https://mcp.notion.com/sse`.
- Terraform remains configured through Docker but still needs token/auth repair.
- Ghidra bridge help remains available from `D:`.
- Unity stdio bridge help remains available through `uvx`.

## Semgrep and Prompt Optimizer
- `semgrep --version` now succeeds from `C:\Users\Prekzursil\.local\bin\semgrep.exe`.
- `node --check tools/editor/prompt-optimizer-button/extension.js` passes.
- `node tools/editor/prompt-optimizer-button/scripts/smoke-test.js` passes.
- Installed Prompt Optimizer remains `prekzursil-local.prompt-optimizer-button@0.1.0`.
