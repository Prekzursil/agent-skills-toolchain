# Editor Tools

`tools/editor/` is the live home for editor-local tooling such as VS Code extensions and vendored host-local orchestration frameworks.

Use this surface for projects that run inside an editor host rather than as MCP-native servers or browser-mediated tools. Keep the runtime boundary, installation path, and validation steps explicit.

Current live editor tool projects:

- [`ralph-orchestrator/`](ralph-orchestrator/README.md) - vendored upstream Ralph Orchestrator snapshot plus local install, MCP registration, and cross-agent skill wiring helpers for Codex, Claude, and Gemini.
