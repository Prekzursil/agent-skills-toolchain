---
name: chatgpt5-web-curate
description: Use when the user explicitly wants final curation or selection performed through the direct ChatGPT web lane, such as "have ChatGPT pick the best one" or "use chatgpt5_web_curate". Prefer the `chatgpt5_web_curate` or `chatgpt_web_curate` tool.
---

# ChatGPT 5 Web Curate

Use the direct ChatGPT web curation lane.

## Behavior
- Prefer `chatgpt5_web_curate`.
- Use for final comparison or recommendation through the ChatGPT web bridge.
- If readiness or session-state checks fail, surface the error clearly.
