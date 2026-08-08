---
name: codex-orchestrate
description: Route a task to Codex on the MCP rail by intent - one skill, all modes. Trigger phrases - 'brainstorm/discuss/coordinate/review/audit/curate/triage with Codex', 'get a Codex second opinion', 'have Codex split roles and combine', 'pick the best option with Codex', 'Codex risk/gap audit', 'Codex governance call'. The rail is the official codex mcp-server - mcp__codex__codex to start a thread, mcp__codex__codex-reply to continue by threadId. There is no per-mode tool - the mode is framed in the prompt, and multi-peer modes are parallel calls the caller synthesizes. Replaces the per-mode wrappers codex-audit, codex-brainstorm, codex-coordinate, codex-curate, codex-consult, codex-discuss, codex-fix, codex-governance, codex-review, and codex-triage. For per-call scoping (model, sandbox, MCP allowlist, --output-schema) use codex-invoke instead.
license: MIT
---

# Codex Orchestrate

One skill for reaching Codex on the **MCP rail**. Read the **mode** from the user's intent,
then dispatch it as a framing inside a single `mcp__codex__codex` call.

**Rebased 2026-08-09.** This skill used to map each mode to a distinct `codex_*` MCP tool
(`codex_brainstorm`, `codex_discuss`, `codex_coordinate`, `codex_review`, `codex_curate`,
`codex_consult`). Those tools were exposed by `tools/mcp/codex-orchestrator/`, which was
deleted with the rest of the ChatGPT-web lane; they were never mounted on any registered
server even before that. **The mode is now a prompt framing, not a tool name.**

## The rail

- `mcp__codex__codex` - start a Codex thread.
- `mcp__codex__codex-reply` - continue by `threadId`. The name is **hyphenated**; the
  underscore form does not resolve.

Each invocation is single-threaded and fresh-context. State that must persist goes in the
prompt or in a file - there is no server-side session store any more.

## Modes - what to put in the prompt

| Intent / trigger | Mode | How to dispatch |
|---|---|---|
| Generate ideas, options, or approaches | `brainstorm` | ask for N distinct options with tradeoffs, or fan out 2 parallel calls with different framings and synthesize |
| Debate tradeoffs, pros and cons, X vs Y | `discuss` | 2 parallel calls with opposed framings, then synthesize yourself |
| Split a task across roles and consolidate | `coordinate` | 1 call per role in parallel, then consolidate yourself |
| Review or critique a plan / design / diff | `review` | 1 call: hand over the artifact, ask for a critic pass with severities |
| Audit for risk, gaps, blind spots | `audit` | same as `review`, framed as "what is missing / what could fail" |
| Pick the single best option from candidates | `curate` | 1 call: hand over the option set, ask for a selection plus justification |
| A governance decision weighing options vs risks | `governance` | same as `curate`, framed against the stated constraints |
| Fast classification of next steps | `triage` | 1 call: ask for an ordered shortlist, nothing else |

(`audit`==`review`, `governance`==`curate`, and a fix path is just `coordinate`; the labels
exist so the router matches the user's wording.)

## Behavior

- Keep the task scoped and decision-oriented; pass one clear prompt.
- Pick the mode from the user's verb; default to `review` for a generic "have Codex look at
  this".
- **You are the synthesizer.** The retired server did multi-peer debate and consolidation
  server-side; on this rail you fan out the calls and combine the results.
- Say which rail you used and whether the final synthesis was yours or Codex's.

## Not this skill

- **Per-call scoping** - restricting a run's MCP servers, sealing its base, allowlisting its
  skills, or taking structured `--output-schema` output - use **`codex-invoke`** (exec rail).
  The MCP rail inherits the full base and cannot scope.
- **Codex environment / session troubleshooting** - `codex-runtime-recovery`,
  `codex-session-reunion`, `codex-vscode-host-routing`.
- **A browser-mediated ChatGPT web lane** - retired 2026-08-09, no replacement in this repo.

## Replaces

Supersedes the per-mode wrapper skills `codex-audit`, `codex-brainstorm`,
`codex-coordinate`, `codex-curate`, `codex-discuss`, `codex-fix`, `codex-governance`,
`codex-review`, `codex-triage`, and - since the 2026-08-09 retirement - the
PromptBridge-lane skill `codex-consult`, which is now a redirect tombstone pointing here.
