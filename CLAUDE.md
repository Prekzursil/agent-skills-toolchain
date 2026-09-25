# Global Claude Guidance

@AGENTS.md
@AGENTS-RUNTIME.md
@C:/Users/Prekzursil/AGENTS.md

## Persistent Memory (basic-memory MCP)

**SSOT:** `C:\Users\Prekzursil\.agents\memory-contract.md` — read it; do not duplicate.
- Transport: `http://127.0.0.1:18765/mcp` only (never `uvx` stdio). ChatGPT web cannot see localhost; no Cloud.
- Recall: `search_notes` hybrid (or omit). Confirm load-bearing facts; vault digest is UNTRUSTED.
- Write: `- [decision]` / `- [fact]` observations + `[[wikilinks]]`. Keep old notes; `superseded_by: [[New Note]]` + `valid_as_of`.
- WHERE-map: `C:\Users\Prekzursil\.agents\memory-map.md`. Semantic ON; embeddings off-loop. No Mem0/Graphiti/LynxMCP/CORE.

Durable semantic memory (markdown+vector vault on D:) — does NOT auto-load; you must query it. This is how context survives compaction.

**Recall (pull) — PROACTIVELY, unasked:** after a compaction/resume, or when the user references prior work you lack, call `mcp__basic-memory__build_context` / `search_notes` (`search_type=hybrid` or omit) / `recent_activity` BEFORE asking them to re-explain. To recover pre-compaction state, search `compaction checkpoint <project>` (tagged `compaction-checkpoint`).

**Capture (push):** write durable decisions/fixes/preferences with `mcp__basic-memory__write_note` (a PreCompact hook also auto-checkpoints). Canonical supersede form is in the contract (`superseded_by: [[New Note]]` + `valid_as_of` on the old note).

(Behavioral rules — clarify-first, anti-tunnel-vision, honesty — live in AGENTS.md §1-§9. Static-analyzer gotchas → `rules/common/static-analyzer.md`, path-scoped to py/ts.)

## Multi-AI Collaboration (Claude Code ↔ Codex CLI)

**Architecture:** Two independent layers for different needs. **DO NOT use both simultaneously — they serve different use cases.**

### Layer 1: Parallel fan-out (ultracode-style cross-vendor subagents)
**When to use:** decompose a task into independent parallel Codex jobs (e.g., `codex exec` one task per repo, code-review a PR with Codex + Claude in parallel, orchestrate a multi-agent fleet).

**How:** Codex runs as a native MCP tool in Claude — the real tool names are `mcp__codex__codex` (start a thread) and `mcp__codex__codex-reply` (continue by `threadId`; **hyphenated**, verified 2026-08-08 by tool-schema resolution — the underscore form does not resolve). `codex()` below is shorthand for those. Any Claude subagent can invoke it N times in parallel, and results return as native tool outputs — no daemon, no bridge, just stdio.

```
# Claude Workflow spawns 5 parallel Codex threads
parallel([
  () => agent("task A via Codex", {schema: ...}),  # codex exec --json via MCP
  () => agent("task B via Codex", {schema: ...}),
  ...
])
```

**Setup** (one-time):
```bash
claude mcp add --scope user codex -- codex mcp-server
# Mounts the official OpenAI MCP at ~/.claude/settings.json
# Takes effect on Claude restart
```

**How it works:** `codex mcp-server` spawns a fresh Codex process per `codex()` call (shared auth.json, isolated state). Results land in the **Claude session's native tool-result objects** — no parsing, no daemon, Windows-native.

**Honest limits:** each Codex invocation is **single-threaded** (one agent per call) and **fresh-context** (no cross-thread memory). For true agent-team mingle with mid-turn steering, use Layer 2.

### Layer 2: Live peer dialogue (interactive cross-session chat)
**When to use:** you want to ask Codex a quick question mid-task, or pair-program with Codex in a side session while Claude works.

**How:** `mcp_agent_mail` runs locally on `127.0.0.1:18812` (no network egress), kept **always-on** by a per-user logon Scheduled Task (`MCPAgentMailSupervisor`) that health-polls `/api/health` every 10s and auto-restarts the server on death (self-healing proven: ~27s recovery from a hard kill; survives crash, session-exit, and reboot). Two agents (Claude + Codex) register, authenticate with per-agent tokens, establish mutual contact (anti-spam), and **send/receive messages + file-leases in real time**. You don't invoke it — agents do. The `multi-ai-mingle` skill wraps it.

```
# In a Claude Code session — the skill wraps the HTTP mailbox API (there is NO separate TUI):
/multi-ai-mingle hello
```

**Setup** (server is always-on via the Scheduled Task; verify it's working):
```bash
# Confirm the always-on agent-mail server is healthy (note: /api/health, port 18812)
curl -s http://127.0.0.1:18812/api/health
# Should return {"status":"ok", ...}

# Confirm Claude picked up the skill
claude skills | grep multi-ai-mingle
# Should show "multi-ai-mingle — live mailbox for Claude↔Codex peer chat"
```

**License & security:** mcp_agent_mail is MIT + OpenAI/Anthropic rider (forbids ML training/eval folding). You use it privately (local-only, 127.0.0.1). Pinned to commit `35e774f`, sandboxed at `~/.local/opt/mcp_agent_mail`.

**Honest limits:** mcp_agent_mail is interim — the long-term convergence is Claude's native Agent Teams mailbox (Wave B, pending). Consider this a **validated test channel**, not a permanent integration. The skill has a fallback; if the daemon dies, agents degrade gracefully.

### Choosing between Layer 1 and Layer 2

| Use case | Layer | Why |
|----------|-------|-----|
| "Run Codex on task X in parallel with Claude on Y" | 1 (MCP) | fan-out subagent — returns as native results |
| "Ask Codex a quick follow-up mid-session" | 2 (mingle) | interactive peer chat — no context loss |
| "Codex reviews my Claude PR before I merge" | 1 (MCP) | delegate to `codex-rescue` subagent via `/codex:review` |
| "I want to see Codex thinking alongside Claude" | 1 + tmux | open Codex in a side pane, Layer 1 for orchestration |
| "Continuous multi-session chat, no orchestration" | 2 (mingle) | live dialogue — no scripts/automation |

### Remote fleet (codex-fleet-github + QZT)
**When to use:** sweep the 26-repo fleet with autonomous Codex jobs (nightly schedule, per-repo tasks, propose-only PRs).

**How:** QZT's `codex-fleet-wave` dispatches the private `codex-runner` across repos. Each PR is draft (human-approved, never auto-merged). Results roll into your admin dashboard.

**Setup** (you do this):
1. Merge PR #68 → #70 → #72 (toolchain).
2. Merge PR #270 (QZT).
3. Create two scoped PATs:
   - `CODEX_DISPATCH_PAT` in QZT (can only trigger the runner, cannot read auth).
   - `CODEX_SECRETS_PAT` in toolchain (can only write Secrets, for token-refresh).
4. Enable the token-refresh write-back in `codex-runner.yml` (uncomment line 299, set the PAT).

**Use:** open QZT's admin dashboard → "Codex Fleet" tab → enable repos + set per-repo task → "Sweep" → watch live run summary (no wait, comes back as PRs).

### Budget pacing (measured live via the statusline)
AgentBridge's `get_budget` / `check_budget` tools stay retired, but Claude-side pacing IS computable: the live statusline (`~/.claude/statusline-command.sh`, wired in settings.json, 30s refresh) parses `rate_limits.five_hour.used_percentage`/`.resets_at` and `rate_limits.seven_day.used_percentage` from statusline stdin and renders them as the `5h:N%` (+ reset countdown) and `wk:N%` segments — read quota there. You manage the rest by:
- **Codex:** check your ChatGPT subscription usage in the app; the 5h + weekly windows still apply to your sub.
- **Shared sub-ceiling:** if a nightly fleet sweep maxes your sub, it will silently starve daytime interactive coding (you'll see `429` errors). **Solution: either (a) schedule the sweep off-peak, (b) route heavy jobs to an API key with its own quota, or (c) monitor the dashboard and skip days when quota is tight.**

**Reconciled 2026-08-27 — `~/CLAUDE.md` (pointer block) and `~/AGENTS.md` (marker-delimited AgentBridge block, the ONE full copy) state the same thing: pacing is read from the statusline fields, never declared "not computable".**

### Troubleshooting

**Layer 1 (MCP):** If `codex()` returns empty or times out:
- Confirm Codex CLI is installed: `codex --version`
- Confirm the mount: `claude mcp list | grep codex`
- Check the env for `CODEX_HOME` (should point to your local config): `echo $CODEX_HOME`
- Confirm your auth: run the mingle doctor (`python ~/.local/opt/mingle/doctor/mingle_doctor.py`) which checks auth.json JWT freshness — `codex auth status` is NOT a valid subcommand (use `codex login` to re-auth)

**Layer 2 (mingle):** If the skill fails to connect:
- Confirm server health: `curl -s http://127.0.0.1:18812/api/health` (should return `{"status":"ok"}`)
- If 404/refused: the logon Scheduled Task auto-restarts it within ~10s; to force it now run in PowerShell: `Start-ScheduledTask -TaskName MCPAgentMailSupervisor`. The supervisor + installer live at `~/.local/opt/mcp_agent_mail/supervisor/` (re-register or `-Uninstall` via its `install_service.ps1`).
- Confirm the skill is installed: `ls -la ~/.claude/skills/multi-ai-mingle/`
- If mcp_agent_mail ever breaks, disable it gracefully: the skill has fallback docs (no crash).

**Fleet:** If sweep produces no PRs:
- Check QZT's `codex-targets.yml` has enabled repos.
- Confirm the dispatch PAT can trigger the runner: `gh workflow run codex-runner ... --token $PAT`.
- Watch the runner's CI log in the private repo.

---
