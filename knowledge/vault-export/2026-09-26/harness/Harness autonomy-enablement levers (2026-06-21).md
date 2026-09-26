---
title: Harness autonomy-enablement levers (2026-06-21)
type: note
permalink: main/harness/harness-autonomy-enablement-levers-2026-06-21
tags:
- harness
- enablement
- autonomy
- mcp-routing
- skill-router
---

# Harness autonomy-enablement levers (2026-06-21)

Grounded in HARNESS-AUDIT-2026-06-21.json (.result.sota_rubric), settings.json, skill-router/route.py, .mcp-disabled-defaults.json.

## Key grounding facts
- Permissions ALREADY fully open: settings.json permissions.defaultMode=bypassPermissions, allow/deny/ask all empty, skipDangerousModePermissionPrompt=true. So "allowlist to reduce confirmations" is a SOLVED problem — NOT the autonomy win. The real friction is tool DISCOVERY, not permission prompts.
- Two-tier MCP: only tavily + github_cli eager; other 46 of 48 servers deferred behind mcp-funnel discover_tools_by_words/load_toolset + ToolSearch (ENABLE_TOOL_SEARCH=auto:5). Agent pays a discovery round-trip every time it needs one of 46 servers, every session (no sticky toolset).
- skill-router/route.py: deterministic IDF keyword scoring over ~248 SKILL.md descriptions + a STATIC 8-entry MCP keyword map (schrodinger, rdkit, tooluniverse, scholarly, RE, basic-memory, web, sonar). Misses ~40 servers. Single-shot per prompt. No outcome learning. Threshold sc>=3.0, top-4.
- goal-reinject: PreToolUse hot-path on Edit|Write|Bash, every 8 write-ops injects goal, every 24 injects falsify-check. Lightweight.
- tool-preflight: SessionStart existence-check only; does NOT pre-warm or surface a per-project tool loadout.
- CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70 (aggressive); CLAUDE_CODE_FORK_SUBAGENT=1; agent teams enabled.
- 995-line skill manifest; ~18 agents; Workflow tool; basic-memory.

## Highest-leverage enablement ideas (NON-guardrail)
1. Auto-generated MCP keyword map (close router's 8/48 coverage gap) — derive all 48 from ToolUniverse/tool descriptions, IDF-rank.
2. Sticky session-aware toolset pre-warm — persist last-used MCP loadout per project, load_toolset eagerly at SessionStart so the agent skips the discovery round-trip.
3. Outcome-learning router — log which injected skill/MCP the agent actually invoked; reweight; promote consistently-used pairs to eager.
4. Restorable-compression note before autocompact at 70% — PreCompact spills re-fetchable handles (paths/URLs/tool-result indices) so agent doesn't re-derive.
5. Per-project tool-loadout manifest — a .claude-loadout that names the 5-10 skills/MCPs this repo needs, surfaced at SessionStart.
6. Model-initiated capability-gap escalation — a tiny "I need a tool for X" affordance that runs discover_tools_by_words and returns a shortlist, closing the active-discovery loop.
