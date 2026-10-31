---
title: multi-agent-quickstart
type: note
permalink: dqverify-repo-20261013/docs/multi-agent-quickstart
---

# Multi-Agent Quickstart

This is the shortest mental model for using the system without getting lost.

> **Rewritten 2026-08-09.** The previous version routed everything through six
> `codex_consult` / `codex_brainstorm` / `codex_review` / `codex_discuss` /
> `codex_coordinate` / `codex_curate` MCP tools plus an optional PromptBridge talk lane.
> Those tools were exposed by `tools/mcp/codex-orchestrator/`, which has been deleted, and
> the talk lane went with it. Nothing below is a rename of the old surface — the tool names
> genuinely no longer exist, so calling them fails rather than degrading.

## First rule

Start simple. Do not jump straight to the most complicated tool.

## The one rail

Codex is reached through the official `codex mcp-server`, mounted at user scope:

- `mcp__codex__codex` — start a Codex thread.
- `mcp__codex__codex-reply` — continue an existing thread by `threadId`
  (the name is hyphenated; the underscore form does not resolve).

There is no per-mode tool any more. **The mode is framed in the prompt**, not selected by a
tool name:

| Old tool | Now |
|---|---|
| `codex_consult` | one `mcp__codex__codex` call asking for one strong answer |
| `codex_brainstorm` | one call asking for N alternatives before deciding |
| `codex_review` | one call handing over the plan/diff and asking for a critic pass |
| `codex_discuss` | two parallel calls with opposed framings, synthesized by the caller |
| `codex_coordinate` | one call per role, fanned out in parallel, consolidated by the caller |
| `codex_curate` | one call handed the option set, asked to select and justify |

Fan-out replaces the orchestration server: launch several `mcp__codex__codex` calls in
parallel and synthesize the results yourself. Each invocation is single-threaded and
fresh-context, so state that must persist belongs in the prompt or in a file, not in the
tool.

## Beginner path

1. Start with the `multi-agent-quickstart` skill.
2. Make one `mcp__codex__codex` call and read the answer.
3. Ask for alternatives in a second call if one answer is not enough.
4. Ask for a critic pass before risky implementation.
5. Hand the option set back for selection when choosing among options.

## After planning

If the work is ready to execute, choose the execution path explicitly:

- subagent-driven execution for complex work, which is the recommended path
- inline execution when the task is small or subagents would be overhead

This keeps the handoff visible instead of silently forcing a single route.

## Failure behavior

There is no second lane to fall back to. If `mcp__codex__codex` is unavailable, say so and
stop — do not silently answer as if a Codex peer had been consulted. Diagnose with
`codex --version` and `claude mcp get codex` (expect `Connected`).