---
name: codex-local-curate
description: Use when the user explicitly wants Codex orchestration to select or synthesize the best option, such as "curate these choices" or "use codex_local_curate". Prefer the `codex_local_curate` or `codex_orchestrator_curate` tool.
---

# Codex Local Curate

Use the Codex orchestration curation flow.

## Behavior
- Prefer `codex_local_curate`.
- Use for final selection among alternatives.
- If PromptBridge ChatGPT web curation fails, fallback to Codex synthesis and say so.
