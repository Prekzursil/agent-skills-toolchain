---
name: multi-ai-mingle
description: Use when the user wants seamless local collaboration between Claude Code
  and OpenAI Codex on the same machine - fanning out parallel Codex coding threads
  from Claude as native MCP tool calls via the official codex mcp-server, and running
  a live symmetric two-way chat and file-lease channel between the two agents through
  mcp_agent_mail. Covers mounting codex-as-MCP at user scope, standing up the shared
  agent-mail http channel, verifying it before use, and the sequenced adoption waves.
  Triggers include mingle Claude and Codex, run Codex from Claude in parallel, set
  up the agent mail channel, replace AgentBridge, or coordinate the two local AI agents.
  Not for single-agent work or remote or cloud multi-agent orchestration.
permalink: dqverify-repo-20261013/skills/multi-ai-mingle/skill.dot.alt
---

# multi-ai-mingle

Seamless LOCAL mingling of Claude Code and OpenAI Codex on one Windows 11 machine. Two
complementary rails:

- **Fan-out rail (Claude drives Codex):** the official `codex mcp-server` (stdio) mounted into
  Claude at user scope. Claude subagents call `mcp__codex__codex` / `mcp__codex__codex_reply` as
  native tools, so one Claude orchestrator can run several parallel Codex coding threads.
- **Live channel rail (peer chat + coordination):** `mcp_agent_mail` (2k-star, maintained;
  FastMCP + Git + SQLite) as a shared http server both agents connect to — symmetric inboxes,
  threads, and advisory file leases. This replaces the Windows-broken AgentBridge.

Keep the two rails distinct: fan-out is command-and-control (Claude tasks Codex); the channel is
peer messaging + file-lease coordination that either side reads and writes.

## When to use
- The user wants Claude and Codex to collaborate locally, in parallel, with a real back-channel.
- The user asks to "run Codex from Claude", "set up the agent-mail channel", or "replace AgentBridge".

## When NOT to use
- Single-agent tasks (just use Claude, or Codex, directly).
- Remote / cloud multi-agent fleets (different tooling).

---

## Real mcp_agent_mail API sequence (VERIFIED 2026-07-11 — the prep draft under-specified this)
The channel is not "just send_message". The working order, proven by the verify probe on Windows:
1. `ensure_project(human_key=<abs path>)` FIRST — creates the namespace. (The **other** tools take
   that same path as `project_key`; only ensure_project uses `human_key`.)
2. `register_agent(project_key, program=<role>, model)` per agent. **Bare role names `claude`/`codex`
   are rejected** — the server assigns an adjective+noun codename (e.g. `BlackCompass`) AND returns a
   `registration_token`. Capture BOTH from the result.
3. First contact is **gated (anti-spam)**: `request_contact(from_agent, to_agent, registration_token)`
   then the recipient `respond_contact(to_agent, from_agent, accept=true, registration_token)`.
4. Then `send_message(sender_name, sender_token, to=[...])`, `fetch_inbox(agent_name, registration_token)`,
   `file_reservation_paths(agent_name, registration_token, paths)` — each call carries the agent's token
   (a single MCP session can only be auto-bound to one agent; pass tokens explicitly for the rest).
In real use each of Claude/Codex has its OWN session bound to its OWN agent, so it authenticates once and
omits the token thereafter; the two-in-one-session token-passing above is a probe artifact.

## Wave A — mount + channel (STATUS: DONE + VERIFIED 2026-07-11)
- ✅ codex mcp-server mounted (user scope, Connected). ✅ mcp_agent_mail installed+pinned+probe-GREEN
  (symmetric both ways + file-lease). ✅ AgentBridge retired (`claude plugin disable agentbridge@agentbridge`).
- ⚠️ Retiring AgentBridge also removed its `get_budget` tool → the CLAUDE.md budget-pacing protocol is
  now inert (was already dormant — daemon down). Re-enable the plugin if budget-pacing is wanted back.


1. **Mount codex-as-MCP (user scope).** See `MOUNT.md`.
   - `claude mcp add --scope user codex -- codex mcp-server`
   - Set a long tool timeout (Codex turns take minutes): `MCP_TOOL_TIMEOUT=600000` and
     `MCP_TIMEOUT=30000` in `~/.claude/settings.json` env, or bake a per-server `timeout` via
     `claude mcp add-json`.
   - Verify: `claude mcp get codex`; ask Claude to run a trivial codex turn.

2. **Stand up the shared agent-mail http channel.** See `MCP_AGENT_MAIL.md`.
   - Install (native Windows): clone, `uv python install 3.14`, `uv venv -p 3.14`, `uv sync`.
   - Run ONE shared server: `uv run python -m mcp_agent_mail.cli serve-http --host 127.0.0.1 --port 8812`.
     (8812 is canonical; 8765 is the LIVE basic-memory port — never collide.)
   - Register the SAME url in both agents: Claude via `claude mcp add --transport http --scope user
     agent-mail http://127.0.0.1:8812/mcp --header "Authorization: Bearer TOKEN"`; Codex via a
     `[mcp_servers.agent-mail]` http block in `~/.codex/config.toml` with `AGENT_NAME` under
     `env_vars`. Identity: `claude` on Claude's side, `codex` on Codex's side.
   - Tools: `send_message`, `fetch_inbox`, `reply_message`, `file_reservation_paths`,
     `release_file_reservations` (plus `register_agent`, `whois`, `list_agents`, `search_messages`).

3. **VERIFY BEFORE RETIRING AGENTBRIDGE.** Run `VERIFY_PLAN.ps1` (native Windows; POSIX mirror
   `VERIFY_PLAN.sh`). It starts an isolated server, proves symmetric claude to codex and codex to
   claude message visibility, and a file-lease acquire/release round-trip, printing SUCCESS: /
   FAILED: lines. Only after all-green: commit the configs and retire AgentBridge.

## Wave B — teammate shim (LATER)
Fork the `claude-anyteam` `CLAUDE_CODE_TEAMMATE_COMMAND` shim into `~/.agents/harness` so Codex can
be launched as a first-class Claude Code teammate (TeamCreate / SendMessage surface), not only an
MCP tool. Gives dispatch parity with native subagents while the agent-mail channel carries the
coordination traffic.

## Wave C — GUI tab (LATER)
Add a GUI tab (agent-mail ships a server-rendered web UI + a TUI console) so the human can watch and
inject into the Claude/Codex thread and see live file leases.

## Wave D — upstream contribution (LATER)
Contribute the AgentBridge fixes upstream (issues #231 / #223) so the learnings from replacing it are
returned to that project rather than just forked away.

---

## Files in this skill
- `MOUNT.md` — exact codex-as-MCP mount + timeout + verify + reverse.
- `MCP_AGENT_MAIL.md` — verified repo, install, dual-agent registration, tool surface, Windows caveats.
- `VERIFY_PLAN.ps1` / `VERIFY_PLAN.sh` / `agent_mail_probe.py` — self-contained symmetric + file-lease smoke test.

## Guardrails
- One shared `serve-http`, not per-client stdio, or the two agents will not see each other's mail.
- Bind agent-mail to `127.0.0.1` and keep the bearer token; do not expose the port.
- Codex turns are long — keep `MCP_TOOL_TIMEOUT` generous or tool calls get cut off mid-turn.
- Python 3.14 + native-Windows wheel builds are the residual risk; the verify step is the gate.
- **Agent identity:** bare role names (`claude`/`codex`) are REJECTED in strict mode — register with
  the role in `program` and address agents by the server-ASSIGNED adjective+noun codename (or pick an
  explicit VALID name like `BlueLake`). Call `ensure_project(human_key=<abs path>)` BEFORE any
  register/send/lease (the rest of the tools take that same path as `project_key`).

## License + adoption posture (owner directive 2026-07-11)
- **License:** mcp_agent_mail is **MIT + an OpenAI/Anthropic rider** — it grants no rights to those two
  vendors/affiliates and its "use" definition forbids incorporating the tool into any **ML training or
  eval pipeline**. For this owner's **private, local** two-agent coordination that is fine (not a
  restricted party, not an eval harness). **Never** fold mcp_agent_mail into an eval/training harness.
- **Pinned + sandboxed + swappable** (the adopt-but-keep-options-open call): vendored at
  `~/.local/opt/mcp_agent_mail`, **pinned to commit `35e774fa9ae636c6e1662ab7925d7e68938bb718`**
  (post-fix for the Windows lock-wedge #91), run **offline** (127.0.0.1, no JWT/share/cloud features).
  The live-channel layer is a thin swappable rail — it **converges onto the Claude Code Agent Teams
  mailbox** once the Wave-B teammate shim lands, so there is no lock-in.
- **Verified facts (this machine, 2026-07-11):** `codex mcp-server` mounted at user scope and reports
  **Connected**; MCP timeouts already generous (`MCP_TOOL_TIMEOUT=300000`, `MCP_TIMEOUT=120000`) — no
  change needed. Note the verify probe uses one connection driving both identities (proves the shared
  store routes + leases); a two-process concurrent test is the deeper follow-up (#91's fix makes it low-risk).