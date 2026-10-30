---
name: 1password-ops
description: 1Password access for agents on Windows — official MCP (secretless, Environments-only), op-personal wrapper (full vault reads via desktop-app integration + one Windows Hello approval), Connect-mode bypass, per-runtime wiring map, fleet item references, token-hygiene rules. Use when a task needs vault credentials, 1Password MCP wiring, or credential-driven automation.
---

# 1password-ops — vault access for the agent estate (Windows)

Two lanes, deliberately different:

## Lane A — official 1Password MCP (`1password-mcp`) — SECRETLESS
- Binary: `C:\Users\Prekzursil\.local\bin\1password-mcp.cmd` (shim → `%LOCALAPPDATA%\Microsoft\WindowsApps\1password-mcp.exe`; the WindowsApps alias survives app updates — the OLD shim pointed at a versioned `Program Files\WindowsApps\Agilebits.1Password_8.12.*` path and broke).
- Enabled by: 1Password desktop → Settings → Developer → **Integrate with MCP clients**.
- Handshake-verified on this machine (rmcp 1.8.0, stdio).
- **It never returns secret values.** Tools: `authenticate`, `list_environments`, `create_environment`, `rename_environment`, `list_variables` (names only), `append_variables`, `create_local_env_file`, `list_local_env_files`. Local `.env` mounts are **macOS/Linux only** — on Windows this MCP is Environments bookkeeping, not credential delivery.
- Wired into (2026-10-21, all backup-first `.bak-1pw`): ZCode `v2/config.json mcp.servers` (restart to load), Claude Code (user-scope `claude mcp add`), Codex `~/.codex/config.toml [mcp_servers.1password]`, OpenCode `~/.config/opencode/opencode.json`, Cursor `~/.cursor/mcp.json`, Windsurf `~/.codeium/windsurf/mcp_config.json`, Grok `~/.grok/config.toml [mcp_servers.1password]`. Antigravity: no local install — wire when installed.

## Lane B — `op-personal` wrapper — FULL VAULT READS (the automation lane)
```bash
~/.local/bin/op-personal <any op command>   # = env -u OP_CONNECT_HOST -u OP_CONNECT_TOKEN op ...
```
- Why: system env forces op into **Connect mode** (service scope, unknown owner — DO NOT remove those vars; bypass only).
- Requires: 1Password desktop running + Settings → Developer → **Integrate with 1Password CLI**. First vault read per unlock-window pops **one Windows Hello prompt** — batch all reads together.
- Account seen: `prekzursil1993@gmail.com` @ my.1password.com. CLI-visible vault (2026-10-21): only `Shared with Grok Bot`. **Vaults not enabled for CLI access are invisible** — if an expected item is missing, enable the vault for CLI (Settings → Developer) or move/copy the item into a CLI-visible vault.
- Credential read pattern: `op-personal item get "<title>" --fields username,password` and `op-personal item get "<title>" --otp` (TOTP at request time — do not cache).

## Fleet item references (grok onboarding)
Intended grok.com/x.ai Login items: prekzursil, prekzursil1993, andreivisalon2002, florineldanciu4, darias.grama, prekzursiltr, dariabonk99, mariusvisalon70, ovido4 (all @gmail.com). As of 2026-10-21 NOT yet visible to the CLI — see vault-access note above.

## Token hygiene (estate rules)
- Secret values from Lane B exist only inside the running process's memory / are passed to the target form — never echoed to logs, never written to disk, never printed in tool output (mask to 4 chars).
- `op://` URIs are the shareable reference form — put them in configs, resolve at runtime.
- Never rotate the grok bridge `credentialEncryptionKey`; never delete its `runtime/data/`.

## Related
- grok-lane skill (bridge runbook) · llm-provider-fleet memory · search-hub-api-keys memory (the ${ENV}-ref doctrine this mirrors)
