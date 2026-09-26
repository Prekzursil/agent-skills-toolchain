---
name: MCP Token Reduction Initiative
description: COMPLETE — reduced MCP overhead by 45% connections (Claude) and 87% servers
  (Codex), all 7 deliverables shipped, benchmark done
type: project
permalink: main/claude-memory/root/project-mcp-reduction
---

Completed initiative to reduce MCP/tool context overhead. All deliverables shipped 2026-04-01.

**Why:** 63 MCP tool sources exposing ~470 tools caused frequent compaction and tool selection degradation.

**Results (2026-04-01):**
- Claude: 20+→11 connected MCP servers (7 plugins disabled)
- Codex: 31→4 default MCP servers (87% reduction)
- 9 duplicate server pairs eliminated
- 4 skill wrappers created (docker-cli, digitalocean-cli, codecov-cli, graphql-cli)
- 4 Codex agent TOMLs created (re-analyst, code-quality-auditor, cloud-deployer, browser-tester)
- 5 subagent dispatch profiles defined
- Meta-tool MCP server built (search_capabilities, describe_tool, execute_tool with lifecycle manager)
- 8-task benchmark: 8/8 capability pass, 6/7 acceptance criteria pass

**Benchmark (2026-04-01):** `enabledPlugins: false` properly removes both MCP connections AND deferred tool names. 132 disabled plugin tools fully excluded. Deferred tools: ~306→~174 (43%). MCP instructions: 7+→3 (57%). All 8 benchmark tasks pass (7/8 full, 1/8 partial — doctl not installed). 7/7 acceptance criteria pass.

**How to apply:**
- All disabled capabilities are restorable via subagent profiles, Codex agent TOMLs, or plugin re-enable
- Meta-tool at `~/.agents/meta-tool/` wraps 6 broad-API servers behind 3 gateway tools
- Run `sync_shared_state.ps1` after any agents.json change

**Key files:**
- Results: `~/docs/plans/2026-04-01-mcp-inventory-results.md`
- Benchmark: `~/docs/plans/2026-04-01-mcp-benchmark-results.md`
- Plan: `~/.claude/plans/joyful-questing-origami.md`
- Design: `~/docs/plans/2026-04-01-mcp-token-reduction-design.md`
- Meta-tool: `~/.agents/meta-tool/`
- Subagent profiles: `~/.agents/subagent-profiles.md`
- Codex agents: `~/.codex/agents/{re-analyst,code-quality-auditor,cloud-deployer,browser-tester}.toml`