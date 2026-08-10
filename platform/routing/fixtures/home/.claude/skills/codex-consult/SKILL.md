---
name: codex-consult
description: Use when the user explicitly wants a Codex-side orchestration pass — consultation, curation, or review — instead of direct ChatGPT web automation. Triggers include "consult/analyze this with Codex", "curate these options with Codex", "review/critique this with Codex", or explicit mentions of codex_local_consult, codex_local_curate, codex_local_review, or the codex_orchestrator_* tools. One skill, three modes.
---

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
- Surface in the result whether ChatGPT-web curation was used secondarily and whether final synthesis stayed on Codex.
- If the user explicitly wants direct ChatGPT-web behavior, do not use this skill — use the `chatgpt-web-*` / `agent-lanes-chatgpt-web-*` lanes instead.
- PromptBridge setup (Windows-only canonical CODEX_HOME): if `codex_local_*` tools are missing, the PromptBridge-backed Codex bridge likely needs installing or probing. Check `CODEX_HOME`, the PromptBridge MCP registration, and the codex-orchestrator MCP before falling back to web lanes.

### PromptBridge setup & verification
### Replaces
