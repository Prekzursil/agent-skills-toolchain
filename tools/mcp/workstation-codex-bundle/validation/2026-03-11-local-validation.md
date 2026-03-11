# 2026-03-11 local validation

## Codex config
- `C:\Users\Prekzursil\.codex\config.toml` parses successfully with Python `tomllib`.
- Serena uses the full Windows `uvx.exe` path and is enabled.
- Notion is enabled; unauthenticated probe returned `401 invalid_token`, which is the expected first-use auth gate.
- Netlify block was removed entirely.
- Terraform remains Docker-backed with `ENABLE_TF_OPERATIONS = "false"` by default.
- MindsDB now targets `http://127.0.0.1:47334/mcp/sse` and `/mcp/status` reports healthy.
- Unity and Ghidra placeholder fail-stubs were replaced with real launch commands and left disabled pending native-app handshake.

## Local installs on D:
- Ghidra, Java 21, Maven, Ghidra MCP repo, Unity MCP repo, and MindsDB storage are all placed on `D:`.

## Prompt Optimizer Button v2
- Packaged and installed as `prekzursil-local.prompt-optimizer-button@0.1.0`.
- No `openExternal` or browser URL remains in the packaged source.
- New commands include optimize/copy/replace/insert, with the old command IDs preserved as compatibility aliases.
