---
name: codex-consult
description: Use when the user explicitly wants a Codex-side orchestration pass — consultation, curation, or review — instead of direct ChatGPT web automation. Triggers include "consult/analyze this with Codex", "curate these options with Codex", "review/critique this with Codex", or explicit mentions of codex_local_consult, codex_local_curate, codex_local_review, or the codex_orchestrator_* tools. One skill, three modes.
---

> ⚠️ **DEPRECATED (2026-07-18): this skill routes to tools that do not exist.** The mounted Codex MCP
> exposes only `mcp__codex__codex` (start a thread) and `mcp__codex__codex-reply` (continue by threadId).
> The `codex_local_consult/curate/review` and `codex_orchestrator_*` tools referenced below were never
> mounted (no PromptBridge server). Use `mcp__codex__codex` directly (frame the mode in the prompt) or the
> `codex-invoke` exec-rail until this skill is rebased onto the real two-tool surface.

# Codex Consult

One skill for the local Codex orchestration lanes. Read the mode from the user's intent — the procedure is the same: dispatch a single scoped prompt to Codex and return its synthesis. There is no need for a separate skill per interaction; the prompt plus the chosen mode determines the behavior.

## Modes

| Mode | Use when | Preferred tool (fallback) |
|---|---|---|
| `consult` | structured analysis, tradeoff review, decision or architecture support | `codex_local_consult` (`codex_orchestrator_consult`) |
| `curate` | compare options and select or synthesize the best one | `codex_local_curate` (`codex_orchestrator_curate`) |
| `review` | critique, audit, or pressure-test a plan or patch | `codex_local_review` (`codex_orchestrator_review`) |

## Behavior

- Keep the task scoped and decision-oriented; pass one clear prompt.
- Prefer the `codex_local_*` tool for the chosen mode; fall back to the matching `codex_orchestrator_*` tool if the local lane is unavailable.

### Replaces
