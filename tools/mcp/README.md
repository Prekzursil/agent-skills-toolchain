# MCP Tools

`tools/mcp/` is the live home for MCP-native tools and adapters.

Put a project here only when it is runnable or clearly bounded enough that its runtime, auth model, and validation path are explicit. Do not use this folder for vague notes or mixed browser automation experiments.

Current bounded projects:

- [`agent-lanes-codex/`](agent-lanes-codex/README.md) - Codex-side orchestration lane with explicit profiles, aliases, and bounded fallback behavior.
- [`workstation-codex-bundle/`](workstation-codex-bundle/README.md) - curated Windows-first MCP bundle with explicit self-made vs curated provenance and validation notes.

Current incubation notes for this surface live under `docs/incubating/tools/`.
