---
name: chatgpt5-web
description: "Direct browser-automation ChatGPT 5 web lane - one skill, three modes via a `mode:` arg. Use when the user explicitly wants the ChatGPT web side (not Codex orchestration): mode:query for a single direct question; mode:discuss to debate/ideate/spar; mode:curate to compare candidates and pick the best. NOT for Codex-side lanes (use codex-consult)."
---

# ChatGPT 5 Web

> ⚠️ **No in-repo implementation (checked 2026-08-09).** The `chatgpt5_web_query` /
> `chatgpt5_web_discuss` / `chatgpt5_web_curate` bridge tools below are **not** provided by
> anything in this repository, and a grep of the pre-retirement tree confirms they never
> were — they were expected from an external bridge. The related in-repo lane
> (`tools/web/agent-lanes-chatgpt-web`, `tools/web/agentify-desktop`) was deleted on
> 2026-08-09, so no local fallback exists either. Before using this skill, verify the three
> tools are actually mounted in your session; if they are not, there is nothing to route to
> and you should say so rather than improvise. For Codex-side work use `codex-orchestrate`.

One skill for the direct browser-mediated ChatGPT 5 web lane. Read the **mode** from the user's
intent (or an explicit `mode:` arg) and call the matching bridge tool.

## Modes

| `mode:` | Use when | Bridge tool |
|---------|----------|-------------|
| `query` | a single direct question or task through ChatGPT web | `chatgpt5_web_query` |
| `discuss` | ideation, sparring, debate, or back-and-forth framing | `chatgpt5_web_discuss` |
| `curate` | final comparison / pick-the-best / recommendation among candidates | `chatgpt5_web_curate` |

## Behavior

- Prefer the bridge tool for the chosen mode (`chatgpt5_web_query` / `chatgpt5_web_discuss` / `chatgpt5_web_curate`).
- Use only when the user explicitly wants the **ChatGPT web** side rather than Codex orchestration. If they want Codex, use the `codex-consult` skill instead.
- Do **not** route to the legacy `agent-lanes-chatgpt-web-*` lanes — deleted 2026-08-09.
- If the session is not ready or a readiness / session-state check fails, surface the error clearly rather than silently proceeding.

> Consolidation note: this skill supersedes the former `chatgpt5-web-query`, `chatgpt5-web-discuss`,
> and `chatgpt5-web-curate` skills. Any older invocation of one of those is now this skill in the
> corresponding mode.
