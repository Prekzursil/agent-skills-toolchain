# MOUNT — codex-as-MCP into Claude Code (USER scope)

Goal: mount the **official** `codex mcp-server` (stdio) into Claude Code at user scope so
Claude (and its subagents) can fan out parallel Codex coding threads as native MCP tool-calls.

Verified ground truth (this machine, 2026-07-11):
- `codex --version` → `codex-cli 0.144.1`
- `codex mcp-server --help` → **"Start Codex as an MCP server (stdio)"** — this is the exact
  server entrypoint. (`codex mcp` — no `-server` — is the *client* manager: `list/get/add/remove/login`.)
- `claude mcp add --help` → supports `--scope user`, `-e/--env`, `-t/--transport` (default stdio).
  There is **no `--timeout` flag** on `claude mcp add` (timeout is set separately — see §2).

---

## 1. Mount command (USER scope)

```bash
claude mcp add --scope user codex -- codex mcp-server
```

- `--scope user` → written to `~/.claude.json` (global, applies in every project / every drive),
  NOT project-local. This is what makes it available to all Claude sessions + subagents.
- Everything after `--` is the literal subprocess argv. `codex mcp-server` inherits
  `~/.codex/config.toml` (model, reasoning effort, MCPs, sandbox) automatically — no ports, no daemon.

### Windows note (native Win11)
`codex` is a native binary on PATH, so the bare `codex mcp-server` spawns fine (unlike `npx`
stdio servers, which hit the Windows spawn bug #64671). If the spawn ever fails with a
"command not found"/spawn error, wrap it through cmd:

```bash
claude mcp add --scope user codex -- cmd /c codex mcp-server
```

…or pin the absolute path (find it with `(Get-Command codex).Source` in PowerShell):

```bash
claude mcp add --scope user codex -- "C:\path\to\codex.exe" mcp-server
```

---

## 2. Long tool-timeout (REQUIRED — Codex coding turns take minutes)

Codex `codex`/`codex_reply` tool calls run a full agent turn (often 1–10 min). Claude Code's
per-tool MCP timeout can cut these off. Two levers (Claude Code **client**-side, values in **milliseconds**):

| Env var | Controls | Suggested value |
|---|---|---|
| `MCP_TOOL_TIMEOUT` | per **tool call** wall-clock limit | `600000` (10 min) |
| `MCP_TIMEOUT` | server **startup** handshake | `30000` (30 s) |
| `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT` | stdio idle-reap window (optional) | `1800000` (30 min, the default) |

Set them **persistently** in `~/.claude/settings.json` so every session inherits them:

```json
{
  "env": {
    "MCP_TOOL_TIMEOUT": "600000",
    "MCP_TIMEOUT": "30000"
  }
}
```

(Progress notifications do **not** extend the per-tool timeout — it is a hard wall-clock limit —
so pick a value comfortably above your longest expected Codex turn.)

### Precise per-server alternative (bakes the timeout into the server entry)
Instead of the plain `add`, register with `add-json`, which accepts a per-server `timeout` field
(ms) that overrides `MCP_TOOL_TIMEOUT` for **this server only**:

```bash
claude mcp add-json --scope user codex '{"type":"stdio","command":"codex","args":["mcp-server"],"timeout":600000}'
```

Use **either** the plain `add` + env vars **or** `add-json` with `timeout` — not both for the same server.

---

## 3. Verify the mount

```bash
# 1. Confirm it is registered at user scope
claude mcp list
claude mcp get codex          # shows command/args; health-checks stdio servers

# 2. In a Claude session, the Codex tools appear namespaced as:
#      mcp__codex__codex          (start a Codex turn)
#      mcp__codex__codex_reply    (continue a Codex thread)
#    Ask Claude to run a trivial Codex turn, e.g. "use the codex tool to print the cwd".
```

A healthy `claude mcp get codex` shows the server connected (not `✗ failed to connect`). If it
fails: check `codex` is on PATH, that `~/.codex/config.toml` parses (`codex mcp-server --strict-config`
surfaces unknown fields), and that `codex login` has a valid session.

---

## 4. Reverse / uninstall

```bash
claude mcp remove --scope user codex
```

Confirm gone with `claude mcp list`. This only unregisters the mount; it does not touch
`~/.codex/config.toml` or the Codex CLI itself. To also roll back the timeout env, delete the two
keys from `~/.claude/settings.json`.

---

## Sources
- Official Codex MCP docs (redirect target of `developers.openai.com/codex/mcp`):
  <https://learn.chatgpt.com/docs/extend/mcp?surface=cli> — confirms `startup_timeout_sec` (10) /
  `tool_timeout_sec` (60) on the *Codex-as-client* side; Codex-as-server command verified locally.
- Codex CLI `mcp` reference: <https://www.mintlify.com/openai/codex/cli/mcp>
- `codex-mcp-server` internals: <https://deepwiki.com/openai/codex/6.4-mcp-server-implementation-(codex-mcp-server)>
- Claude Code MCP + timeout env vars: <https://code.claude.com/docs/en/mcp>,
  issue #47076 (`MCP_TOOL_TIMEOUT`), #16837 (`MCP_TIMEOUT`), #64671 (Windows stdio spawn).
- Local verification: `codex mcp-server --help`, `claude mcp add --help` (codex-cli 0.144.1).
