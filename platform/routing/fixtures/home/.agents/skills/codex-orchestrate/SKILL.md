---
name: codex-orchestrate
description: Route a task to the right Codex (codex-as-MCP) orchestration tool by intent - one skill, all modes. Trigger phrases - 'brainstorm/discuss/coordinate/review/audit/curate/triage with Codex', 'get a Codex second opinion', 'have Codex split roles and combine', 'pick the best option with Codex', 'Codex risk/gap audit', 'Codex governance call'. Maps intent to the codex_* tool + profile - brainstorm ideas (codex_brainstorm), debate tradeoffs (codex_discuss), split-roles or fix-path (codex_coordinate), review or audit a plan/diff (codex_review), curate or govern a final pick (codex_curate), fast triage of next steps (codex_consult). Replaces the per-mode wrappers codex-audit, codex-brainstorm, codex-coordinate, codex-curate, codex-discuss, codex-fix, codex-governance, codex-review, and codex-triage. For the local PromptBridge consult/curate/review lanes use codex-consult instead.
license: MIT
---

> ⚠️ **DEPRECATED (2026-07-18): this skill routes to tools that do not exist.** The mounted Codex MCP
> exposes only `mcp__codex__codex` and `mcp__codex__codex-reply`. The `codex_brainstorm/discuss/coordinate/
> review/curate/consult` profile tools mapped below were never mounted on any registered server. Use
> `mcp__codex__codex` directly (frame the intent/role in the prompt) or the `codex-invoke` exec-rail until
> this skill is rebased onto the real two-tool surface.

# Codex Orchestrate

One skill for the **codex-as-MCP** orchestration tools. Read the **mode** from
the user's intent and call the matching `codex_*` tool with its profile — the
procedure is identical across modes (dispatch one scoped prompt, return Codex's
synthesis). There is no need for a separate skill per interaction; the prompt
plus the chosen mode determines the behavior.

## Modes

| Intent / trigger | Mode | Tool (profile) |
|---|---|---|
| Generate ideas, options, or approaches | `brainstorm` | `codex_brainstorm` (brainstorm) |
| Debate tradeoffs, pros and cons, X vs Y | `discuss` | `codex_discuss` (discuss) |
| Split a task across roles and consolidate; coordinate a fix path | `coordinate` | `codex_coordinate` (coordinate) |
| Review or critique a plan / design / diff before building | `review` | `codex_review` (review) |
| Audit for risk, gaps, blind spots, and what needs verifying | `audit` | `codex_review` (review) |
| Pick the single best option from candidates (final selector) | `curate` | `codex_curate` (curate) |

### Behavior
### Not this skill
### Replaces
