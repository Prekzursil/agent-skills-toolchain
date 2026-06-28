---
name: chatgpt5-web-query
description: Use when the user explicitly invokes chatgpt5_web_query or asks to query ChatGPT 5 web directly for a single question or task ; do NOT use for the legacy agent-lanes-chatgpt-web-query route ; returns ChatGPT 5 web query answer.
---

# ChatGPT 5 Web Query

Use the direct browser-automation ChatGPT web lane.

## Behavior
- Prefer `chatgpt5_web_query`.
- Use when the user explicitly wants the ChatGPT web side rather than Codex orchestration.
- If the session is not ready, surface that clearly.
