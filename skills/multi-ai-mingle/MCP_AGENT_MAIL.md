# MCP Agent Mail — research + Windows install/registration

Purpose (Wave A #2): adopt `mcp_agent_mail` as the **live symmetric Claude ↔ Codex chat channel**
(replacing the Windows-broken AgentBridge). This is the "Gmail for coding agents" layer:
identities, inboxes, searchable threads, and advisory file leases.

## Vaporware filter — VERIFIED REAL & MAINTAINED

| Field | Value |
|---|---|
| **Repo (locked for Wave A)** | <https://github.com/Dicklesworthstone/mcp_agent_mail> |
| Description | "Asynchronous coordination layer for AI coding agents: identities, inboxes, searchable threads, and advisory file leases over FastMCP + Git + SQLite" |
| Stars | **2021** |
| Archived? | **No** |
| Last push | **2026-06-27** (repo touched 2026-07-11) |
| Open issues | 0 |
| License | non-standard (GitHub reports `NOASSERTION` — a LICENSE file exists but is not an SPDX-standard id; **read it before redistributing**) |
| Author | Jeffrey Emanuel (jeffreyemanuel.com) |
| Listed on | PulseMCP ("Agent Mail MCP Server") |
| Supported agents (per README) | Claude Code, Codex CLI, Gemini CLI, GitHub Copilot CLI, any MCP client |

Sibling project (NOT used in Wave A, noted for awareness): **`Dicklesworthstone/mcp_agent_mail_rust`**
— a Rust rewrite, 34 tools, TUI console, ~100 stars, pushed 2026-07-11 (actively developed). The
Python original is stable/mature; stick with Python per the locked plan. Revisit Rust later if the
Python Py3.14 dependency chain proves painful on native Windows.

**Verdict: real, mature (2k★), actively maintained. Not vaporware.**

---

## Architecture (decisive for how we wire it)

- Backend = **SQLite index + Git-backed archive** under a single `STORAGE_ROOT`
  (default `~/.mcp_agent_mail_git_mailbox_repo`). **All agents share state through that one store.**
- **Two transports:**
  - `serve-http` (Streamable-HTTP, upstream-default port 8765 but **we run it on 8812** — 8765 is the LIVE basic-memory port — bearer-token auth) — **RECOMMENDED for
    multi-agent.** One shared server; Claude and Codex both connect to the same URL and therefore
    see each other's mail. **This is the transport Wave A uses.**
  - `serve-stdio` — host-spawned private child, logs to stderr. Fine for a single client, but two
    separate stdio children would each be their own process (state only shared via the on-disk
    STORAGE_ROOT, with concurrent-writer risk). **Do NOT use stdio for the symmetric channel** —
    use one shared `serve-http`.
- Identity = **`AGENT_NAME` env var** (e.g. `claude`, `codex`), overridable per call via the
  `sender_name` / `agent_name` tool parameters.

> Design consequence: the live channel is **one long-running `serve-http` process** on
> `127.0.0.1:8812`; Claude registers it as an **http** MCP server and Codex registers the **same
> URL**. Both authenticate with the same bearer token. Messages flow through the shared SQLite/git store.

---

## Install on native Windows 11

Requires **Python 3.14** + **uv** + **Git for Windows**. Core send/inbox/lease functionality runs
**native (no WSL)**; WSL is only implicated by the *optional* git pre-commit guard hooks.

```powershell
git clone https://github.com/Dicklesworthstone/mcp_agent_mail
cd mcp_agent_mail
uv python install 3.14
uv venv -p 3.14
.\.venv\Scripts\activate
uv sync
```

Alternatives:
- **pipx (single user):** `pipx install git+https://github.com/Dicklesworthstone/mcp_agent_mail.git`
- **One-line installer (bash — auto-detects agents, auto-wires configs):**
  `curl -fsSL "https://raw.githubusercontent.com/Dicklesworthstone/mcp_agent_mail/main/scripts/install.sh?$(date +%s)" | bash -s -- --yes`
  (bash-only; on native Windows prefer the explicit `uv` steps above so nothing silently edits configs.)

### Launch the shared channel
```powershell
# Isolated data dir recommended so the smoke test / channel is reproducible:
$env:STORAGE_ROOT = "$env:USERPROFILE\.mcp_agent_mail_git_mailbox_repo"
uv run python -m mcp_agent_mail.cli serve-http --host 127.0.0.1 --port 8812
```
On startup it prints (and writes to `$STORAGE_ROOT\.env`) the bearer token. Grab it:
```powershell
Select-String -Path "$env:STORAGE_ROOT\.env" -Pattern "BEARER"
```
(The exact key name is one of `HTTP_BEARER_TOKEN` / `INTEGRATION_BEARER_TOKEN` depending on
version — grep for `BEARER` rather than assuming. The VERIFY script auto-discovers it.)

---

## Register with BOTH agents (same shared URL)

### Claude Code (`~/.mcp.json` or via CLI)
CLI (user scope):
```bash
claude mcp add --transport http --scope user agent-mail http://127.0.0.1:8812/mcp \
  --header "Authorization: Bearer YOUR_TOKEN_HERE"
```
Equivalent `~/.mcp.json` block:
```json
{
  "mcpServers": {
    "agent-mail": {
      "type": "http",
      "url": "http://127.0.0.1:8812/mcp",
      "headers": { "Authorization": "Bearer YOUR_TOKEN_HERE" }
    }
  }
}
```
Set Claude's identity so `AGENT_NAME` defaults to `claude` for this session (shell env, or a
`send_message(sender_name="claude", …)` per call).

### Codex CLI (`~/.codex/config.toml`)
Either `codex mcp add agent-mail …` or edit `config.toml` directly. Note the **`env_vars` form**
so `${VAR}` are passed literally (Codex does NOT expand `${VAR}` inline — set them under `env`/`env_vars`):
```toml
[mcp_servers.agent-mail]
type = "http"
url  = "http://127.0.0.1:8812/mcp"

[mcp_servers.agent-mail.headers]
Authorization = "Bearer YOUR_TOKEN_HERE"

# Identity for Codex's side of the channel:
[mcp_servers.agent-mail.env_vars]
AGENT_NAME = "codex"
```
(If this Codex build only accepts stdio MCP servers in `config.toml`, register agent-mail via
`codex mcp add` with the http transport, or point Codex at a thin stdio shim — but current Codex
0.144.x supports http MCP servers, so the block above is the path.)

---

## Tool surface (exact registered MCP tool names — deepwiki-grounded)

**Messaging**
- `send_message(project_key, sender_name, to=[…], subject, body_md, cc?, bcc?, importance?, ack_required?, thread_id?, attachment_paths?, sender_token?)`
- `fetch_inbox(project_key, agent_name, limit?, urgent_only?, include_bodies?, since_ts?, registration_token?)`
- `reply_message(…)` — reply within a thread
- `acknowledge_message(…)` — mark acknowledged
- `search_messages(…)`, `summarize_thread(…)`

**Identity / discovery**
- `register_agent(project_key, program, model, name, …)` — create a named identity in a project
- `whois(…)`, `list_agents(…)`
- `macro_start_session(--human-key, --program, --model, --agent-name?, --task-description?)` — CLI
  macro that does `ensure_project` + `register_agent` + inbox fetch in one shot

**Advisory file leases**
- `file_reservation_paths(project_key, agent_name, paths=[…], ttl_seconds?, exclusive?, reason?)` — acquire
- `release_file_reservations(project_key, agent_name, paths?=[…] | file_reservation_ids?=[…])` — release
- `force_release_file_reservation(…)` — clear a stale lease held by an inactive agent
- CLI read helpers: `file_reservations list | active | soon`

> `project_key` = the **absolute path to a project directory** (the coordination namespace).
> The mutating operations are exposed as **MCP tools over the http JSON-RPC endpoint**, so the
> faithful test/driver path is an MCP client call, not a bespoke CLI mutation subcommand.

---

## Windows caveats & open questions (feed the VERIFY-then-commit gate)

1. **Python 3.14 requirement** is bleeding-edge; `uv` installs it, but confirm every dependency
   builds a native-Windows wheel under 3.14 during `uv sync` (watch for source-build failures).
2. **Bearer-token env-key name** is version-dependent (`HTTP_BEARER_TOKEN` vs `INTEGRATION_BEARER_TOKEN`).
   Auto-discover by grepping `BEARER` in `$STORAGE_ROOT\.env`.
3. **Exact tool parameter names** (`sender_name`/`from_agent`, `agent_name`) are grounded in
   deepwiki over the repo, not pinned to a byte-exact source read of the mounted version — the
   VERIFY script exercises them live and reports the precise failure if any name differs.
4. **Git "dubious ownership"** can bite the git-archive step under bind-mounts/odd ownership — add
   the STORAGE_ROOT to `git config --global --add safe.directory`. Native (non-container) use is
   usually fine.
5. **Optional pre-commit guard hooks** are the only feature flagged as WSL-leaning; skip them for
   Wave A (we only need send/inbox/lease over http).
6. **Auth on localhost** — the http server expects a bearer token; do not disable it. Bind to
   `127.0.0.1` only.

## Confidence
- Repo real / maintained / tool surface / transport model: **HIGH** (2k★, verified via GitHub API +
  deepwiki over source + README).
- Native-Windows core send/inbox/lease working out-of-the-box: **MEDIUM-HIGH** — architecture is
  Windows-friendly (pure-Python http, file-backed), but Py3.14 wheel-build + exact token-key/param
  names are the residual unknowns. **This is exactly why Wave A is VERIFY-then-commit** — run
  `VERIFY_PLAN.ps1` before retiring AgentBridge.

## Sources
- Repo + metadata (GitHub API): <https://github.com/Dicklesworthstone/mcp_agent_mail>
  (stars/pushed_at/archived verified live 2026-07-11)
- README (install / registration / tool surface): <https://raw.githubusercontent.com/Dicklesworthstone/mcp_agent_mail/main/README.md>
- Transport / CLI / tool-name / shared-state / Windows facts: deepwiki over `Dicklesworthstone/mcp_agent_mail`
- Author project page: <https://jeffreyemanuel.com/projects/mcp-agent-mail>
- Listing: <https://www.pulsemcp.com/servers/dicklesworthstone-agent-mail>
