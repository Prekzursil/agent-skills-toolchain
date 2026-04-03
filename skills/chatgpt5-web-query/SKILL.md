---
name: chatgpt5-web-query
description: Use when the user explicitly wants a direct ChatGPT 5 web/Agentify interaction, such as "ask ChatGPT directly", "use chatgpt5_web_query", or "send this to ChatGPT web". Prefer the `chatgpt5_web_query` or `chatgpt_web_query` tool.
---

# ChatGPT 5 Web Query

Use the direct browser-automation ChatGPT web lane.

## Behavior
- Prefer `chatgpt5_web_query`.
- Use when the user explicitly wants the ChatGPT web side rather than Codex orchestration.
- If the session is not ready, surface that clearly.
