---
title: research claude-code-mcp nested delegation 2026-09-22
type: report
permalink: main/research/research-claude-code-mcp-nested-delegation-2026-09-22
tags:
- research-report
- claude-code-mcp
- workflows
- agent-hygiene
- medium-high
---

# Research: nested-Claude delegation in workflows (claude-code-mcp) — 2026-09-22

Incident: 2 of 20 wave agents in wf_c8e4c79c-1c8 (WebCoder wave) called mcp__claude-code-mcp__claude_code 12x, guarded only by prompt text ("READ-ONLY task…"); 10 calls read-only, 2 wrote the agent's own deliverable with read-guards. UNVERIFIED whether permissionMode was ever passed.

## Findings (graded)
- [fact] steipete/claude-code-mcp ARCHIVED May 15 2026, read-only upstream [A.primary README]. Last feature: permissionMode option.
- [fact] Default is --dangerously-skip-permissions; permissionMode (default/acceptEdits/auto/dontAsk/plan) is opt-in PER CALL, no server-side enforcement. README: "This wrapper is not an OS-level sandbox" [A.primary].
- [fact] Author's own alternatives section: for Claude Code as the caller prefer native --allowedTools/--disallowedTools or `claude mcp serve` [A.primary].
- [fact] Official permissions doc: deny rules accept globs — "mcp__*" denies all MCP tools; deny removes tool from context; order deny>ask>allow. Settings skips parenthesized mcp__ rules (param-matching needs --disallowedTools CLI) [A.official].
- [fact, corrob x4 blogs/plugin-docs, NOT official-changelog-verified] Claude Code v2.1.172 (2026-06-10) added NATIVE nested subagents up to 5 deep; depth dial CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH [C.corrob].
- [fact] anthropics/claude-code issue #68619: recursive spawn = top operational pain in agent fleets [B.github].
- [fact] gruckion/nested-subagent plugin documents the same workaround class: native Task tool blocked nesting -> claude -p headless escape hatch [B.github].

## Decision ranking
1. REPLACE (deny mcp__claude-code-mcp for agent contexts + use native nesting/agent() where delegation is wanted)
2. Ban-only (subsumed by 1)
3. OS-sandbox the child container (README's own hard-boundary suggestion; heavy)
4. Keep + prompt-harden (status quo — weakest; caller-controlled opt-in = no structural guarantee)

## Gems
- CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH env dial (verify on our build before relying).
- Transcript grep discriminator: catalog-mention vs "name":"mcp__server__tool" tool_use = cheap fleet behavior audit.
- `claude mcp serve` = official native path for non-Claude hosts (the legit niche of claude-code-mcp).

Sources: steipete/claude-code-mcp README (github.com/steipete/claude-code-mcp), code.claude.com/docs/en/permissions, code.claude.com/docs/en/iam, code.claude.com/docs/en/agent-sdk/permissions, github.com/anthropics/claude-code/issues/68619, github.com/gruckion/nested-subagent, ofox.ai/blog/claude-code-nested-subagents-2026, claudefa.st/blog/guide/agents/nested-subagents, claudemap.org subagents guide. Providers: firecrawl (McpHub 404, searxng unresolved). Confidence: Medium-High.
