# Tools

This repo separates tool work into three live surfaces:

- `mcp/` for MCP-native tools and adapters
- `editor/` for editor-local tools such as VS Code extensions
- `web/` for browser- or web-mediated tools

Those surfaces stay distinct because they have different auth, runtime, packaging, and validation models. Concepts that are not runnable yet belong under `docs/incubating/tools/`, not here.
