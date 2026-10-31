---
name: multi-agent-quickstart
description: Use when learning how to reach Codex from this Windows-first setup -
  the beginner mental model for the codex mcp-server rail (mcp__codex__codex / mcp__codex__codex-reply),
  how the retired per-mode codex_* tools map onto prompt framings, when to fan out
  parallel calls instead, and how to choose an execution path after planning.
permalink: dqverify-repo-20261013/skills/multi-agent-quickstart/skill
---

# Multi-Agent Quickstart

**Rewritten 2026-08-09.** The previous version taught six MCP tools (`codex_consult`,
`codex_brainstorm`, `codex_review`, `codex_discuss`, `codex_coordinate`, `codex_curate`) plus
an optional PromptBridge talk lane. All of them came from `tools/mcp/codex-orchestrator/` and
`tools/web/promptbridge-talk-lane/`, both deleted. These are not renames - the old tool names
fail rather than degrade.

## Mental model

There is **one rail**: the official `codex mcp-server`.

- `mcp__codex__codex` - start a Codex thread.
- `mcp__codex__codex-reply` - continue by `threadId` (hyphenated; the underscore form does
  not resolve).

The old tool names are now prompt framings on that one rail:

| Old tool | Now |
|---|---|
| `codex_consult` | one call asking for one strong answer |
| `codex_brainstorm` | one call asking for N alternatives |
| `codex_review` | one call handing over the plan/diff, asking for a critic pass |
| `codex_discuss` | two parallel calls with opposed framings, synthesized by you |
| `codex_coordinate` | one call per role in parallel, consolidated by you |
| `codex_curate` | one call handed the option set, asked to select and justify |

Fan-out replaces the orchestration server. Each call is single-threaded and fresh-context, so
anything that must persist belongs in the prompt or in a file.

## Beginner flow

1. Make one `mcp__codex__codex` call and read the answer.
2. Ask for alternatives in a second call if one answer is not enough.
3. Ask for a critic pass before a risky implementation.
4. Hand the option set back for selection when choosing among options.

## Execution choice

- After planning, prefer subagent-driven execution for complex work.
- Use inline execution when the task is small or subagents would be overhead.
- Do not silently force one path after the plan is written.

## Failure behavior

There is no second lane to fall back to, and no `fallback_to_lane_a` flag. If the rail is
unavailable, say so and stop - do not answer as though a Codex peer had been consulted.
Diagnose with `codex --version` and `claude mcp get codex` (expect `Connected`).

## Related skills

`codex-orchestrate` (mode routing on this rail) · `codex-invoke` (exec rail, per-call
scoping) · `codex-consult` (retired tombstone, redirects here).