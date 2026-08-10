---
name: chatgpt5-web
description: >
  Direct browser-automation ChatGPT 5 web lane — one skill, three modes selected by a `mode:` arg
  (query / discuss / curate). Use when the user explicitly wants the ChatGPT web side (not Codex
  orchestration): mode:query for a single direct question or task (chatgpt5_web_query); mode:discuss
  to debate, ideate, or spar back-and-forth (chatgpt5_web_discuss); mode:curate to compare candidates
  and pick or recommend the best (chatgpt5_web_curate). Do NOT use for the legacy
  agent-lanes-chatgpt-web-* routes or for Codex-side lanes (use codex-consult for those).
---

# ChatGPT 5 Web

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
- Do **not** route to the legacy `agent-lanes-chatgpt-web-*` lanes.
- If the session is not ready or a readiness / session-state check fails, surface the error clearly rather than silently proceeding.

> Consolidation note: this skill supersedes the former `chatgpt5-web-query`, `chatgpt5-web-discuss`,
> and `chatgpt5-web-curate` skills. Any older invocation of one of those is now this skill in the
> corresponding mode.
