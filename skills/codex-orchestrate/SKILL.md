---
name: codex-orchestrate
description: Route a task to the right Codex (codex-as-MCP) orchestration tool by intent - one skill, all modes. Trigger phrases - 'brainstorm/discuss/coordinate/review/audit/curate/triage with Codex', 'get a Codex second opinion', 'have Codex split roles and combine', 'pick the best option with Codex', 'Codex risk/gap audit', 'Codex governance call'. Maps intent to the codex_* tool + profile - brainstorm ideas (codex_brainstorm), debate tradeoffs (codex_discuss), split-roles or fix-path (codex_coordinate), review or audit a plan/diff (codex_review), curate or govern a final pick (codex_curate), fast triage of next steps (codex_consult). Replaces the per-mode wrappers codex-audit, codex-brainstorm, codex-coordinate, codex-curate, codex-discuss, codex-fix, codex-governance, codex-review, and codex-triage. For the local PromptBridge consult/curate/review lanes use codex-consult instead.
license: MIT
---

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
| A final governance decision weighing options against risks | `governance` | `codex_curate` (curate) |
| Fast classification of next steps before deeper work | `triage` | `codex_consult` (consult) |

(`audit`==`review`, `governance`==`curate`, and a fix path is just `coordinate`;
the labels are there so the router matches the user's wording.)

## Behavior

- Keep the task scoped and decision-oriented; pass one clear prompt.
- Pick the mode from the user's verb (brainstorm / discuss / coordinate / review
  / audit / curate / govern / triage); default to `review` for a generic
  "have Codex look at this".
- For multi-peer modes (`brainstorm`, `discuss`) Codex runs two peers then
  synthesizes; for `coordinate` it splits roles and consolidates one outcome.
- Return Codex's synthesis; note whether final synthesis stayed on Codex.

## Not this skill

- **Local PromptBridge lanes** (`codex_local_consult` / `codex_local_curate` /
  `codex_local_review`, with `codex_orchestrator_*` fallback) — use
  **`codex-consult`**. That is a separate tool family (PromptBridge-backed),
  intentionally kept apart from these codex-as-MCP tools.
- **Direct ChatGPT-web** behavior — use the `chatgpt5-web-*` lanes.
- **Codex environment / session troubleshooting** — use `codex-runtime-recovery`,
  `codex-session-reunion`, or `codex-vscode-host-routing`.

## Replaces

Supersedes the redundant per-mode wrapper skills, each of which was a single line
pointing at one `codex_*` tool: `codex-audit`, `codex-brainstorm`,
`codex-coordinate`, `codex-curate`, `codex-discuss`, `codex-fix`,
`codex-governance`, `codex-review`, and `codex-triage`.
