# Cursor CLI bridges (Windows) — run Claude Code & Codex on your Cursor subscription

Run **Claude Code CLI** and **Codex CLI** on Windows against the **Cursor** model backend, authenticated
with your **existing Cursor desktop session token** — no OAuth, no new credentials, no WSL.

> **Scope / ToS note:** this routes your *own* CLIs through your *own* Cursor subscription using the token
> the desktop app already holds. It uses a community proxy that adapts Cursor's backend; Cursor does not
> officially sanction non-Cursor clients, so treat this as a personal, gray-area convenience. It does **not**
> mint new credentials, change any account/team settings, or touch the live `state.vscdb`.

## How it works

One Node proxy — [auth2api](https://github.com/AmazingAng/auth2api) — runs natively on Windows at
`http://127.0.0.1:8317` and serves **both** CLIs from one Cursor token:

- **Anthropic** `/v1/messages` → for Claude Code CLI
- **OpenAI** `/v1/responses` → for Codex CLI

The desktop `cursorAuth/accessToken` + `refreshToken` are imported into the proxy's local token store. The
proxy translates to Cursor's backend (`api2.cursor.sh`). Location: `Cowork\tools\auth2api`; a local gate key
(`cursor-local-key`) is what the CLIs send to the proxy — it is **not** a Cursor credential.

## The four commands

| Command | Backend | Notes |
|---|---|---|
| `claude` | normal Anthropic | untouched |
| `claude-cursor` | **Cursor** | Claude Code via the proxy |
| `codex` | normal | untouched |
| `codex-cursor` | **Cursor** | Codex via the proxy (`--profile cursor`) |

The `-cursor` launchers live in a dir on `PATH` (`~\.local\bin`), pass through all args/flags, and
**auto-start the proxy** if it isn't already listening (on-invoke; no scheduled task). Plain `claude` and
`codex` are never shadowed and keep using their normal backends.

### Usage

```powershell
claude-cursor -p "your prompt"            # Claude Code on Cursor
codex-cursor exec --skip-git-repo-check -s read-only "your prompt"   # Codex on Cursor (non-interactive)
codex-cursor                               # interactive Codex on Cursor
```

Verified with live prompts: `claude-cursor` returned `CLAUDE_BRIDGE_OK`; `codex-cursor` returned
`CODEX_BRIDGE_OK` / `LAUNCHER_OK`.

## Known limitation — Codex agentic tool-calling

Codex over this bridge works for **text, reasoning, and code drafting**, but **not autonomous tool-calling**
(`apply_patch` / shell loops). Cursor's chat backend (as surfaced by the proxy) returns text + reasoning only
and does not emit OpenAI `function_call` items, so Codex won't drive an agentic editing loop here. For full
agentic Codex, use plain `codex` on its native backend. **Claude Code (`claude-cursor`) does not have this
limitation** for its normal message flow.

## Durability (no repeated SSO)

The desktop token is a single rolling, **non-rotating, auto-renewing** session credential (fresh ~60-day
expiry on each refresh); normal Cursor use keeps it alive indefinitely. If idle for weeks, refresh it with
`Cowork\private\cursor-token-refresh.mjs` (mints a fresh token, backs it up, never touches `state.vscdb`),
then re-import into the proxy. Interactive **web dashboard** access is the one thing still requiring a real
web login — the token cannot mint a `type:"web"` session.

## Start / stop / revert

```powershell
# start the proxy manually (the -cursor launchers also auto-start it)
Cowork\tools\auth2api\start-proxy.ps1

# revert Claude  → stop using claude-cursor (nothing global changed)
# revert Codex   → delete ~\.codex\cursor.config.toml (main config.toml is untouched)
# remove launchers → delete claude-cursor.* / codex-cursor.* from ~\.local\bin
```

## Files

- Proxy: `Cowork\tools\auth2api\` (config.yaml, start-proxy.ps1, ensure-proxy.ps1, imported token store)
- Launchers: `~\.local\bin\{claude-cursor,codex-cursor}.{ps1,cmd}`
- Codex profile: `~\.codex\cursor.config.toml` (standalone; main `config.toml` unchanged)
- Full setup writeup with proofs: `Cowork\output\cli-bridges-windows_2026-08-25.md`
