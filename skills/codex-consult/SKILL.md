---
name: codex-consult
description: RETIRED 2026-08-09 - redirect tombstone. The PromptBridge/Agentify Codex-side consultation lane this skill drove was deleted from the repo; its codex_local_consult / codex_local_curate / codex_local_review and codex_orchestrator_* tools do not exist and cannot be mounted. Kept only so in-flight invocations of the old name resolve. For a Codex consult / curate / review pass use codex-orchestrate (MCP rail) or codex-invoke (exec rail, per-call scoping); both ride mcp__codex__codex / mcp__codex__codex-reply.
license: MIT
---

# Codex Consult - RETIRED (redirect tombstone)

**Do not follow the old procedure. There is nothing to route to.**

This skill routed to a local PromptBridge-backed Codex bridge. On 2026-08-09 the five trees
that implemented it were deleted from this repo - `tools/mcp/codex-orchestrator`,
`tools/mcp/agent-lanes-codex`, `tools/web/agentify-desktop`,
`tools/web/promptbridge-talk-lane`, `tools/web/agent-lanes-chatgpt-web`. The tools it named
(`codex_local_consult` / `codex_local_curate` / `codex_local_review`, with
`codex_orchestrator_*` as fallback) were already unmounted before that; now the code behind
them is gone too.

## Use instead

| You wanted | Use |
|---|---|
| a consult / curate / review pass on the MCP rail | **`codex-orchestrate`** - one `mcp__codex__codex` call, mode framed in the prompt |
| the same, but scoped (model, sandbox, MCP allowlist, `--output-schema`) | **`codex-invoke`** - the exec rail; never hand-roll `codex exec` argv |
| the beginner mental model for choosing | **`multi-agent-quickstart`** |

The rail is the official `codex mcp-server`: `mcp__codex__codex` starts a thread,
`mcp__codex__codex-reply` continues one by `threadId` (hyphenated - the underscore form does
not resolve). There is no per-mode tool; parallel calls replace the retired fan-out server.

## Why a tombstone and not a deletion

The name is deployed to the live harness and may still be invoked. A tombstone resolves and
redirects; a missing skill fails opaquely. Same pattern as `design-review-loop`.
