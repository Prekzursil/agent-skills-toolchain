# Repo guidance for Claude Code

## AgentBridge is RETIRED — do not follow the old protocol

This file previously carried an `<!-- AgentBridge:start -->` block instructing agents to
coordinate through AgentBridge and to call its MCP tools (`reply`, `get_messages`,
`get_budget`). **Those tools no longer exist.** AgentBridge was Windows-broken and was
disabled (`claude plugin disable agentbridge@agentbridge`); its daemon does not run. Acting
on the old instructions makes an agent call removed tools and wait for a peer that is not
listening — which is why the block was removed rather than left in place as history.

**Two rails replace it.** Both are documented, with setup and a verify-before-trust probe,
in the `multi-ai-mingle` skill (`skills/multi-ai-mingle/SKILL.md`):

1. **Fan-out (Claude to Codex).** The official `codex mcp-server` is mounted at user scope,
   so `mcp__codex__codex` / `mcp__codex__codex-reply` are native tools. Launch several in
   parallel for independent Codex threads; results return as ordinary tool results.
2. **Live peer channel.** `mcp_agent_mail` runs locally on `127.0.0.1:8812` for symmetric
   Claude/Codex messaging plus advisory file leases.

**Consequence worth knowing:** retiring AgentBridge also removed `get_budget`, so the
automated budget-pacing enforcement is gone. Budget pacing is now advisory and manual — see
`agent-self/config/CLAUDE.md`, which already records this.

Repository conventions (structure, build and test commands, style, PR expectations) live in
[`AGENTS.md`](AGENTS.md).
