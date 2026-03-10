# Web Tools

`tools/web/` is the live home for browser- or web-mediated agent tooling.

Put a project here only when it has a clear session model, runtime boundary, and validation path. Do not mix MCP-native transport work into this surface.

Current bounded project:

- [`agent-lanes-chatgpt-web/`](agent-lanes-chatgpt-web/README.md) - direct ChatGPT web lane with explicit session, readiness, and lane-routing behavior.

Current incubation notes for this surface live under `docs/incubating/tools/`.
