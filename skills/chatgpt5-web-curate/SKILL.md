---
name: chatgpt5-web-curate
description: Use when the user explicitly invokes chatgpt5_web_curate or asks ChatGPT 5 web to pick the best option among candidates ; do NOT use for the legacy agent-lanes-chatgpt-web-curate route or Codex-side curation ; returns ChatGPT 5 web curation selection.
---

# ChatGPT 5 Web Curate

Use the direct ChatGPT web curation lane.

## Behavior
- Prefer `chatgpt5_web_curate`.
- Use for final comparison or recommendation through the ChatGPT web bridge.
- If readiness or session-state checks fail, surface the error clearly.
