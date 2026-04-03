---
name: codex-local-consult
description: Use when the user explicitly wants a structured Codex-side consultation pass, such as "consult", "analyze this with Codex", or "use codex_local_consult". Prefer the `codex_local_consult` or `codex_orchestrator_consult` tool instead of direct ChatGPT web tools.
---

# Codex Local Consult

Use a Codex orchestration consultation pass for structured analysis.

## Behavior
- Prefer `codex_local_consult`.
- Keep the task scoped and decision-oriented.
- Mention whether ChatGPT web curation is enabled in the result metadata.
- If the user wants pure direct ChatGPT web behavior, do not use this skill.
